"""Scan only intended public assets and generated artifacts, never private account files."""
import json
from pathlib import Path

from agent_cost_down.privacy import public_export, scrub

roots = [Path("frontend/public"), Path("frontend/dist"), Path("schemas")]
checked = 0
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".js", ".css", ".html", ".txt"}:
            continue
        source = path.read_text()
        if path.suffix == ".json":
            public_export(json.loads(source))
        elif scrub(source) != source:
            raise SystemExit("Publication blocked: secret-shaped text in " + str(path))
        checked += 1
print(f"Checked {checked} public files. Manual prompt review remains a separate release gate.")
