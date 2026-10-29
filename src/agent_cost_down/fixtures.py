from __future__ import annotations

import copy
import json
import random
from datetime import date, timedelta
from pathlib import Path

from .contracts import PublicTask, digest

FAMILIES = ["resolution", "amendment", "returns", "analysis", "ambiguity"]
GROUPS = {
    "resolution": {"development": "color_alias", "heldout": "size_alias"},
    "amendment": {"development": "absolute_quantity", "heldout": "relative_quantity"},
    "returns": {"development": "ordinary_return", "heldout": "previous_partial_return"},
    "analysis": {"development": "units_per_order", "heldout": "value_date_filter"},
    "ambiguity": {"development": "missing_quantity_or_stock", "heldout": "missing_request_or_variant_stock"},
}


def base_state(i, rng):
    products = [
        {"sku": "BLUE-M", "name": "Everyday tee", "color": "blue", "size": "medium", "unit_cents": 2500},
        {"sku": "BLACK-M", "name": "Everyday tee", "color": "black", "size": "medium", "unit_cents": 2500},
        {"sku": "BLACK-L", "name": "Everyday tee", "color": "black", "size": "large", "unit_cents": 2700},
        {"sku": "MUG", "name": "Studio mug", "color": "white", "size": "standard", "unit_cents": 1800},
    ]
    return {
        "products": sorted(products, key=lambda r: r["sku"]),
        "stock": [
            {"sku": p["sku"], "available": rng.randint(12, 30)}
            for p in sorted(products, key=lambda r: r["sku"])
        ],
        "orders": [
            {"id": f"O{i}", "customer_id": f"C{i}", "status": "open", "created_at": "2026-10-20"},
            {"id": f"O{i}B", "customer_id": f"C{i}", "status": "delivered", "created_at": "2026-10-10"},
            {"id": f"O{i}X", "customer_id": "OTHER", "status": "open", "created_at": "2026-10-20"},
        ],
        "lines": [
            {"id": f"L{i}", "order_id": f"O{i}", "sku": "BLUE-M", "quantity": 2, "returned": 0},
            {"id": f"L{i}B", "order_id": f"O{i}", "sku": "MUG", "quantity": 1, "returned": 0},
            {"id": f"L{i}C", "order_id": f"O{i}B", "sku": "BLACK-M", "quantity": 3, "returned": 0},
            {"id": f"L{i}X", "order_id": f"O{i}X", "sku": "MUG", "quantity": 7, "returned": 0},
        ],
    }


def expected_change(state, operation, line_id, value):
    """Independent reference arithmetic, never calls runtime mutation code."""
    expected = copy.deepcopy(state)
    line = next(r for r in expected["lines"] if r["id"] == line_id)
    stock = {r["sku"]: r for r in expected["stock"]}
    if operation == "replace":
        stock[line["sku"]]["available"] += line["quantity"]
        stock[value]["available"] -= line["quantity"]
        line["sku"] = value
    elif operation == "quantity":
        stock[line["sku"]]["available"] += line["quantity"] - value
        line["quantity"] = value
    elif operation == "return":
        stock[line["sku"]]["available"] += value
        line["returned"] += value
    return expected


def generate(root: Path, seed=20261024, *, quantity_base=3, return_days=30, as_of="2026-10-24"):
    if (root / "manifest.json").exists():
        raise ValueError("Fixture manifest already exists; choose a new directory to preserve immutability")
    if not 3 <= quantity_base <= 10 or not 14 <= return_days <= 90:
        raise ValueError("Generator quantities or return window are outside supported ranges")
    today = date.fromisoformat(as_of)
    manifest = {
        "schema_version": 1,
        "seed": seed,
        "generator_version": "3",
        "groups": GROUPS,
        "parameters": {"quantity_base": quantity_base, "return_days": return_days, "as_of": as_of},
        "tasks": [],
    }
    for family_index, family in enumerate(FAMILIES):
        for variant in range(8):
            rng = random.Random(seed + family_index * 10000 + variant * 100)
            i = 1000 + family_index * 100 + variant * 3 + rng.randint(0, 2)
            split = "development" if variant < 4 else "heldout"
            state = base_state(i, rng)
            state["orders"][0]["created_at"] = (today - timedelta(days=4)).isoformat()
            state["orders"][1]["created_at"] = (today - timedelta(days=10)).isoformat()
            expected, resolution, details = copy.deepcopy(state), "changed", {}
            if family == "resolution":
                # Group-disjoint wording and distractors, with shared supported tool capabilities.
                target = "BLACK-M"
                request = f"In order O{i}, replace the blue medium tee with the black tee in the same size. Keep quantities and the mug unchanged."
                if variant >= 4:
                    state["lines"][0]["sku"] = "BLACK-M"
                    target = "BLACK-L"
                    request = f"In O{i}, move my black shirt up from medium to large. Keep its color, quantity, and the other items unchanged."
                expected = expected_change(state, "replace", f"L{i}", target)
                details = {"operation": "replace", "order_id": f"O{i}", "line_id": f"L{i}", "value": target}
            elif family == "amendment":
                qty = quantity_base + variant
                request = f"Change the tee quantity in order O{i} to {qty}. Leave the mug alone."
                if variant >= 4:
                    request = f"I need {qty - 2} additional blue medium tees in O{i}. Everything else stays."
                expected = expected_change(state, "quantity", f"L{i}", qty)
                details = {"operation": "quantity", "order_id": f"O{i}", "line_id": f"L{i}", "value": qty}
            elif family == "returns":
                resolution = "changed"
                if variant >= 4:
                    state["lines"][2]["returned"] = 1
                if variant % 2:
                    state["orders"][1]["created_at"] = (today - timedelta(days=return_days + 5)).isoformat()
                    expected = copy.deepcopy(state)
                    resolution, details = "refused", {"code": "return_window", "order_id": f"O{i}B"}
                    request = (
                        f"Return one tee from my delivered order O{i}B, if the return policy permits it."
                    )
                    if variant >= 4:
                        request = f"I already returned one tee from O{i}B. Please return one more if it is still eligible."
                else:
                    qty = 1 if variant < 4 else 2
                    state["lines"][2]["returned"] = 1 if variant >= 4 else 0
                    request = f"Return {qty} tee{'s' if qty > 1 else ''} from delivered order O{i}B."
                    expected = expected_change(state, "return", f"L{i}C", qty)
                    details = {"operation": "return", "order_id": f"O{i}B", "line_id": f"L{i}C", "value": qty}
            elif family == "analysis":
                resolution = "answer"
                if variant < 4:
                    request = "How many units are in each of my orders? Return order_id and units, sorted by order_id."
                    rows = [
                        {
                            "order_id": o["id"],
                            "units": sum(l["quantity"] for l in state["lines"] if l["order_id"] == o["id"]),
                        }
                        for o in state["orders"]
                        if o["customer_id"] == f"C{i}"
                    ]
                else:
                    cutoff = (today - timedelta(days=9)).isoformat()
                    request = f"For my open orders created since {cutoff}, total the line value in cents. Return a single row with total_cents."
                    # Independently exercise each predicate: an old open order and a recent delivered order.
                    state["orders"].extend([
                        {"id": f"O{i}OLD", "customer_id": f"C{i}", "status": "open",
                         "created_at": (today - timedelta(days=12)).isoformat()},
                        {"id": f"O{i}RECENT", "customer_id": f"C{i}", "status": "delivered",
                         "created_at": (today - timedelta(days=2)).isoformat()},
                    ])
                    state["lines"].extend([
                        {"id": f"L{i}OLD", "order_id": f"O{i}OLD", "sku": "MUG", "quantity": 2, "returned": 0},
                        {"id": f"L{i}RECENT", "order_id": f"O{i}RECENT", "sku": "BLACK-M", "quantity": 1, "returned": 0},
                    ])
                    expected = copy.deepcopy(state)
                    prices = {p["sku"]: p["unit_cents"] for p in state["products"]}
                    ids = {
                        o["id"]
                        for o in state["orders"]
                        if o["customer_id"] == f"C{i}" and o["status"] == "open" and o["created_at"] >= cutoff
                    }
                    rows = [
                        {
                            "total_cents": sum(
                                l["quantity"] * prices[l["sku"]]
                                for l in state["lines"]
                                if l["order_id"] in ids
                            )
                        }
                    ]
                details = {"rows": rows}
            else:
                if variant % 2:
                    target = "BLACK-M" if variant < 4 else "BLACK-L"
                    next(s for s in state["stock"] if s["sku"] == target)["available"] = 0
                    expected = copy.deepcopy(state)
                    request = f"Replace the tee in O{i} with {target} if available. Otherwise refuse without changing anything."
                    resolution, details = "refused", {"code": "out_of_stock", "order_id": f"O{i}"}
                else:
                    request = (
                        f"Change the tee quantity in O{i}." if variant < 4 else "Please update my order."
                    )
                    resolution, details = (
                        "clarification",
                        {"missing": ["quantity"]} if variant < 4 else {"missing": ["request"], "allowed_missing_sets": [["request"], ["request", "order_id"]]},
                    )
            task_id = f"{family}-{split}-{variant % 4 + 1}"
            task = PublicTask(
                id=task_id,
                family=family,
                split=split,
                template_group=GROUPS[family][split],
                request=request,
                customer_id=f"C{i}",
                as_of=as_of,
                snapshot=f"snapshots/{task_id}.json",
                snapshot_hash=digest(state),
                rules={"return_days": return_days, "return_window_anchor": "order.created_at",
                       "return_window_inclusive": True, "amendable_status": "open"},
            )
            oracle = {
                "task_id": task_id,
                "resolution": resolution,
                "expected_state": expected,
                "details": details,
                "review_status": "pending_human_review",
            }
            for path, data in [
                (root / "public" / f"{task_id}.json", task.model_dump()),
                (root / task.snapshot, state),
                (root / "private_expected" / f"{task_id}.json", oracle),
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, indent=2) + "\n")
            manifest["tasks"].append(
                {
                    "id": task_id,
                    "split": split,
                    "family": family,
                    "template_group": task.template_group,
                    "task_hash": digest(task),
                    "oracle_hash": digest(oracle),
                }
            )
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_task(root: Path, task_id: str):
    manifest = json.loads((root / "manifest.json").read_text())
    entries = {t["id"]: t for t in manifest["tasks"]}
    if task_id not in entries:
        raise ValueError("Task is not in the manifest")
    task = PublicTask.model_validate_json((root / "public" / f"{task_id}.json").read_text())
    if digest(task) != entries[task_id]["task_hash"]:
        raise ValueError("Task changed after generation")
    snapshot = json.loads((root / task.snapshot).read_text())
    if digest(snapshot) != task.snapshot_hash:
        raise ValueError("Snapshot changed")
    return task, snapshot


def suite_tasks(root: Path, split: str):
    return [t["id"] for t in json.loads((root / "manifest.json").read_text())["tasks"] if t["split"] == split]


def require_current_suite(root: Path):
    """Reject legacy oracle contracts before any paid inference or reservation."""
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("generator_version") != "3":
        raise ValueError("Live execution requires generator version 3; set ACD_SUITE=fixtures-v3")
