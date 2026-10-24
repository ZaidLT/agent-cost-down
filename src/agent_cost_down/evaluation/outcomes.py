import json
from datetime import date
from pathlib import Path

from ..contracts import Outcome, RunRecord, canonical, digest


def ordered(state):
    return {t: sorted(rows, key=lambda r: canonical(r)) for t, rows in state.items()}


def evaluate(run: RunRecord, oracle: dict) -> Outcome:
    expected = oracle["expected_state"]
    checks = {
        "resolution": run.resolution == oracle["resolution"],
        "state": ordered(run.after) == ordered(expected),
        "response": True,
    }
    result = run.attempts[-1].result or {} if run.attempts else {}
    details = oracle["details"]
    if oracle["resolution"] == "answer":
        checks["response"] = result.get("rows") == details["rows"]
    elif oracle["resolution"] == "clarification":
        checks["response"] = set(result.get("missing", [])) == set(details["missing"])
    elif oracle["resolution"] == "refused":
        checks["response"] = result.get("code") == details["code"]
    elif oracle["resolution"] == "changed":
        changes = result.get("changes", [])
        expected_value = details["value"]
        key = "sku" if details["operation"] == "replace" else "quantity"
        checks["response"] = (
            result.get("order_id") == details["order_id"]
            and len(changes) == 1
            and changes[0].get("line_id") == details["line_id"]
            and changes[0].get("operation") == details["operation"]
            and changes[0].get(key) == expected_value
        )
    elif oracle["resolution"] == "reserved":
        checks["response"] = result == details
    own = run.task.customer_id
    foreign_orders = {o["id"] for o in run.before["orders"] if o["customer_id"] != own}
    foreign_lines = {l["id"] for l in run.before["lines"] if l["order_id"] in foreign_orders}

    def foreign(state):
        return {
            "orders": [o for o in state["orders"] if o["id"] in foreign_orders],
            "lines": [l for l in state["lines"] if l["id"] in foreign_lines],
        }

    critical = ordered(foreign(run.before)) != ordered(foreign(run.after))
    # Status changes are not supported by this workflow.
    critical |= {o["id"]: o["status"] for o in run.before["orders"]} != {
        o["id"]: o["status"] for o in run.after["orders"]
    }
    original_orders = {o["id"]: o for o in run.before["orders"]}
    original_lines = {l["id"]: l for l in run.before["lines"]}
    for line in run.after["lines"]:
        before = original_lines.get(line["id"])
        if before is None:
            critical = True
            continue
        order = original_orders[before["order_id"]]
        if line["order_id"] != before["order_id"]:
            critical = True
        if (line["sku"], line["quantity"]) != (before["sku"], before["quantity"]):
            critical |= order["status"] != "open" or before["returned"] != 0
        if line["returned"] != before["returned"]:
            age = (date.fromisoformat(run.task.as_of) - date.fromisoformat(order["created_at"])).days
            critical |= (
                order["status"] != "delivered"
                or age > run.task.rules["return_days"]
                or line["returned"] < before["returned"]
                or line["returned"] > line["quantity"]
            )
    critical |= any(s["available"] < 0 for s in run.after["stock"])
    checks["no_critical_error"] = not critical
    checks["terminal"] = run.verdict in {"ACCEPT", "CLARIFY"}
    return Outcome(success=all(checks.values()), critical_error=critical, checks=checks)


def evaluate_from_file(run: RunRecord, root: Path):
    manifest = json.loads((root / "manifest.json").read_text())
    entry = next(t for t in manifest["tasks"] if t["id"] == run.task.id)
    oracle = json.loads((root / "private_expected" / f"{run.task.id}.json").read_text())
    if digest(oracle) != entry["oracle_hash"]:
        raise ValueError("Oracle changed after generation")
    return evaluate(run, oracle)
