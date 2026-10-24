from __future__ import annotations

import copy
import json
import re
import sqlite3
from datetime import date
from typing import Any, Literal

from pydantic import Field

from .contracts import Contract, PublicTask, digest


class Empty(Contract):
    pass


class Search(Contract):
    query: str = Field(max_length=100)


class OrderId(Contract):
    order_id: str


class StockQuery(Contract):
    sku: str


class SQLQuery(Contract):
    query: str = Field(max_length=2000)


class Change(Contract):
    operation: Literal["replace", "quantity", "return"]
    line_id: str
    sku: str | None = None
    quantity: int | None = Field(default=None, ge=1, le=100)


class Draft(OrderId):
    changes: list[Change] = Field(min_length=1, max_length=8)


class Answer(Contract):
    rows: list[dict[str, Any]] = Field(max_length=100)


class Clarification(Contract):
    missing: list[Literal["order_id", "variant", "quantity", "request"]] = Field(min_length=1, max_length=4)
    question: str = Field(min_length=1, max_length=300)


class Refusal(Contract):
    code: Literal["out_of_stock", "return_window", "immutable_order"]
    order_id: str
    message: str = Field(min_length=1, max_length=300)


class Reservation(Contract):
    sku: str
    quantity: int = Field(ge=1, le=100)


TOOL_TYPES = {
    "search_products": Search,
    "list_orders": Empty,
    "get_order": OrderId,
    "check_stock": StockQuery,
    "get_rules": Empty,
    "read_only_sql": SQLQuery,
    "submit_draft": Draft,
    "submit_answer": Answer,
    "clarify": Clarification,
    "refuse": Refusal,
}
DESCRIPTIONS = {
    "search_products": "Search the product catalog by words, color, size or SKU. Empty query lists products.",
    "list_orders": "List only orders belonging to the authenticated customer.",
    "get_order": "Read an authorized order and its lines.",
    "check_stock": "Read available stock for a SKU.",
    "get_rules": "Read the public amendment and return policy.",
    "read_only_sql": "Run one read-only SQL query on authorized orders, lines, products and stock. Maximum 100 rows.",
    "submit_draft": "Finish with proposed changes. Runtime validation and commit happen after this tool. Use quantity as the desired final quantity, or amount to return.",
    "submit_answer": "Finish with structured query result rows.",
    "clarify": "Finish by asking for genuinely missing information; do not guess.",
    "refuse": "Finish with a refusal supported by the published business rules.",
    "reserve_inventory": "Finish by reserving the specified quantity from inventory.",
}
TERMINAL = {"submit_draft", "submit_answer", "clarify", "refuse", "reserve_inventory"}


class ToolFailure(ValueError):
    pass


class World:
    """Per-attempt SQLite sandbox. Reads expose only the authorized customer's data."""

    def __init__(self, task: PublicTask, snapshot: dict):
        self.task = task
        self.initial = copy.deepcopy(snapshot)
        if digest(snapshot) != task.snapshot_hash:
            raise ValueError("Snapshot hash mismatch")
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
        CREATE TABLE products(sku TEXT PRIMARY KEY, name TEXT, color TEXT, size TEXT, unit_cents INTEGER);
        CREATE TABLE stock(sku TEXT PRIMARY KEY, available INTEGER);
        CREATE TABLE orders(id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT);
        CREATE TABLE lines(id TEXT PRIMARY KEY, order_id TEXT, sku TEXT, quantity INTEGER, returned INTEGER);
        """)
        for table in ("products", "stock", "orders", "lines"):
            for row in snapshot[table]:
                cols = ",".join(row)
                marks = ",".join("?" for _ in row)
                self.db.execute(f"INSERT INTO {table}({cols}) VALUES({marks})", list(row.values()))
        self.db.commit()
        self.db.row_factory = sqlite3.Row

    def close(self):
        self.db.close()

    def state(self):
        return {
            t: [dict(r) for r in self.db.execute(f"SELECT * FROM {t} ORDER BY 1")]
            for t in ("products", "stock", "orders", "lines")
        }

    def types(self):
        if self.task.adapter == "inventory":
            return {"search_products": Search, "check_stock": StockQuery, "reserve_inventory": Reservation}
        return TOOL_TYPES

    def tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": n,
                    "description": DESCRIPTIONS[n],
                    "parameters": typ.model_json_schema(),
                },
            }
            for n, typ in self.types().items()
        ]

    def order(self, order_id):
        row = self.db.execute(
            "SELECT * FROM orders WHERE id=? AND customer_id=?", (order_id, self.task.customer_id)
        ).fetchone()
        if row is None:
            raise ToolFailure("Order is unavailable in the authorized scope")
        return dict(row)

    def read(self, name, args):
        if name == "search_products":
            words = args.query.lower().split()
            return [
                dict(r)
                for r in self.db.execute("SELECT * FROM products ORDER BY sku")
                if all(w in " ".join(str(v) for v in r).lower() for w in words)
            ]
        if name == "list_orders":
            return [
                dict(r)
                for r in self.db.execute(
                    "SELECT * FROM orders WHERE customer_id=? ORDER BY id", (self.task.customer_id,)
                )
            ]
        if name == "get_order":
            return {
                **self.order(args.order_id),
                "lines": [
                    dict(r)
                    for r in self.db.execute(
                        "SELECT * FROM lines WHERE order_id=? ORDER BY id", (args.order_id,)
                    )
                ],
            }
        if name == "check_stock":
            row = self.db.execute("SELECT * FROM stock WHERE sku=?", (args.sku,)).fetchone()
            if row is None:
                raise ToolFailure("Unknown SKU")
            return dict(row)
        if name == "get_rules":
            return {**self.task.rules, "as_of": self.task.as_of}
        if name == "read_only_sql":
            return self.read_sql(args.query)
        raise ToolFailure("Unknown read tool")

    def read_sql(self, query):
        # Use a separate authorized projection, so arbitrary joins cannot reveal other customers.
        scoped = sqlite3.connect(":memory:")
        self.db.backup(scoped)
        scoped.execute(
            "DELETE FROM lines WHERE order_id NOT IN (SELECT id FROM orders WHERE customer_id=?)",
            (self.task.customer_id,),
        )
        scoped.execute("DELETE FROM orders WHERE customer_id<>?", (self.task.customer_id,))
        scoped.commit()
        scoped.row_factory = sqlite3.Row
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        }
        tables = {"products", "stock", "orders", "lines"}

        def authorize(action, arg1, arg2, database, trigger):
            if action == sqlite3.SQLITE_READ and arg1 not in tables:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in {
                "load_extension",
                "readfile",
                "writefile",
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        scoped.set_authorizer(authorize)
        steps = 0

        def progress():
            nonlocal steps
            steps += 1
            return int(steps > 100)

        scoped.set_progress_handler(progress, 1000)
        try:
            result = [dict(r) for r in scoped.execute(query).fetchmany(101)]
            if len(result) > 100 or len(json.dumps(result)) > 16000:
                raise ToolFailure("Query output exceeds limits")
            return result
        except sqlite3.Error as exc:
            raise ToolFailure("Read-only query rejected or exceeded its budget") from exc
        finally:
            scoped.close()

    def finish(self, name, args):
        if name == "clarify":
            return "CLARIFY", "clarification", args.model_dump()
        if name == "submit_answer":
            if len(json.dumps(args.rows)) > 16000:
                raise ToolFailure("Answer too large")
            return "ACCEPT", "answer", args.model_dump()
        if name == "refuse":
            order = self.order(args.order_id)
            if args.code == "return_window":
                if (
                    date.fromisoformat(self.task.as_of) - date.fromisoformat(order["created_at"])
                ).days <= self.task.rules["return_days"]:
                    raise ToolFailure("Return window has not expired")
            elif args.code == "immutable_order" and order["status"] == "open":
                raise ToolFailure("Order is amendable")
            # Out-of-stock semantic relevance is checked independently after execution.
            return "ACCEPT", "refused", args.model_dump()
        if name == "reserve_inventory":
            with self.db:
                cur = self.db.execute(
                    "UPDATE stock SET available=available-? WHERE sku=? AND available>=?",
                    (args.quantity, args.sku, args.quantity),
                )
                if cur.rowcount != 1:
                    raise ToolFailure("Insufficient stock")
            return "ACCEPT", "reserved", args.model_dump()
        if name != "submit_draft":
            raise ToolFailure("Unknown terminal tool")
        order = self.order(args.order_id)
        if len({c.line_id for c in args.changes}) != len(args.changes):
            raise ToolFailure("Duplicate line changes")
        with self.db:
            for change in args.changes:
                row = self.db.execute(
                    "SELECT * FROM lines WHERE id=? AND order_id=?", (change.line_id, args.order_id)
                ).fetchone()
                if row is None:
                    raise ToolFailure("Line is unavailable")
                line = dict(row)
                if change.operation == "return":
                    age = (date.fromisoformat(self.task.as_of) - date.fromisoformat(order["created_at"])).days
                    if order["status"] != "delivered" or age > self.task.rules["return_days"]:
                        raise ToolFailure("Return is not allowed")
                    qty = change.quantity
                    if qty is None or change.sku is not None or qty > line["quantity"] - line["returned"]:
                        raise ToolFailure("Invalid return quantity")
                    self.db.execute("UPDATE lines SET returned=returned+? WHERE id=?", (qty, line["id"]))
                    self.db.execute("UPDATE stock SET available=available+? WHERE sku=?", (qty, line["sku"]))
                    continue
                if order["status"] != "open" or line["returned"]:
                    raise ToolFailure("Order cannot be amended")
                sku, qty = line["sku"], line["quantity"]
                if change.operation == "replace":
                    if change.sku is None or change.quantity is not None:
                        raise ToolFailure("Replacement requires only a SKU")
                    sku = change.sku
                elif change.operation == "quantity":
                    if change.quantity is None or change.sku is not None:
                        raise ToolFailure("Quantity change requires only quantity")
                    qty = change.quantity
                self.db.execute(
                    "UPDATE stock SET available=available+? WHERE sku=?", (line["quantity"], line["sku"])
                )
                cur = self.db.execute(
                    "UPDATE stock SET available=available-? WHERE sku=? AND available>=?", (qty, sku, qty)
                )
                if cur.rowcount != 1:
                    raise ToolFailure("Insufficient stock or unknown SKU")
                self.db.execute("UPDATE lines SET sku=?,quantity=? WHERE id=?", (sku, qty, line["id"]))
        return "ACCEPT", "changed", args.model_dump()


def validated_pointer(name: str | None, path: str | None, arguments: dict, types: dict):
    if name is None:
        return path is None
    if name not in types:
        return False
    if path is None:
        return True
    if not path.startswith("/") or len(path) > 128:
        return False
    schema = types[name].model_json_schema()
    value: Any = arguments
    current = schema
    for part in path[1:].split("/"):
        if re.search(r"~(?![01])", part):
            return False
        part = part.replace("~1", "/").replace("~0", "~")
        if "$ref" in current:
            current = schema["$defs"][current["$ref"].split("/")[-1]]
        if current.get("type") == "array":
            if (
                not re.fullmatch(r"0|[1-9][0-9]*", part)
                or not isinstance(value, list)
                or int(part) >= len(value)
            ):
                return False
            current, value = current["items"], value[int(part)]
        else:
            if part not in current.get("properties", {}):
                return False
            current = current["properties"][part]
            value = value.get(part) if isinstance(value, dict) else None
    return True
