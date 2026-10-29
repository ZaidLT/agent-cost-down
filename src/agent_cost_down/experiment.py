"""Versioned provenance for the controlled contract rerun, not fresh validation."""
import subprocess

PROTOCOL = "4"
ORIGINAL_REPORT = "555720dd79a2c26c"
DISCLOSURE = (
    "Controlled rerun on the same evaluation suite. These tasks and their v3 results were inspected "
    "before the v4 amendment. This is not fresh independent validation."
)
INTERVENTIONS = ["accept_redundant_fields", "specific_runtime_feedback", "correct_failure_labels"]


def revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def provenance():
    return {
        "protocol_version": PROTOCOL,
        "validator_version": "2",
        "amendment_commit": revision(),
        "interventions": INTERVENTIONS,
        "original_report": ORIGINAL_REPORT,
        "reused_suite": True,
        "evaluation_disclosure": DISCLOSURE,
    }
