"""Check that each credit allocation can hold its worst-case reservations before initializing the ledger.

Run this before `acd doctor --initialize-ledger`. The ledger split is fixed once configured.
"""

import argparse
import json
import math
from pathlib import Path

from agent_cost_down.contracts import POLICIES, Limits, ModelCatalog, policy
from agent_cost_down.ledger import ALLOCATIONS
from agent_cost_down.provider import maximum_cost


def main(args):
    catalog = ModelCatalog.model_validate_json(Path(args.models).read_text())
    limits = Limits(
        output_tokens=args.output_tokens,
        transport_retries=args.transport_retries,
        request_bytes=args.request_bytes,
    )
    maxima = {pid: maximum_cost(policy(catalog, pid, limits)) for pid in POLICIES}
    worst_policy = max(maxima, key=maxima.get)
    worst = maxima[worst_policy]
    pools = {name: args.usable_usd * share for name, share in ALLOCATIONS.items()}
    print(json.dumps({"limits": limits.model_dump(), "per_run_maximum_usd": maxima, "largest_reservation_policy": worst_policy}, indent=2))
    for name, size in pools.items():
        # Admission requires charged + reservation <= allocation, so the last
        # worst-case run must start before charges exceed size - worst.
        headroom = size - worst * args.concurrency
        status = "OK" if headroom >= 0 else "BLOCKED"
        print(
            f"{name:12s} pool ${size:6.2f}  worst-case hold ${worst * args.concurrency:5.2f}  "
            f"prior spend admitting largest policy ${max(headroom, 0):6.2f}  {status}"
        )


def positive_amount(value):
    amount = float(value)
    if not math.isfinite(amount) or amount <= 0:
        raise argparse.ArgumentTypeError("Credit amount must be positive and finite")
    return amount


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="private/models.json")
    parser.add_argument("--usable-usd", type=positive_amount, required=True)
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
    defaults = Limits()
    parser.add_argument("--output-tokens", type=int, default=defaults.output_tokens)
    parser.add_argument("--transport-retries", type=int, default=defaults.transport_retries)
    parser.add_argument("--request-bytes", type=int, default=defaults.request_bytes)
    main(parser.parse_args())
