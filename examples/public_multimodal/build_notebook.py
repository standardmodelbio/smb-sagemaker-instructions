"""Build the distributed notebook from the walkthrough. Buyers use the .ipynb."""

import argparse
import json
import re
from pathlib import Path


def build() -> dict:
    root = Path(__file__).resolve().parents[2]
    document = (root / "PUBLIC_DATA_WALKTHROUGH.md").read_text()
    parts = re.split(
        r"^```python\n(.*?)\n```\s*$", document, flags=re.MULTILINE | re.DOTALL
    )
    cells = []
    for number, part in enumerate(parts):
        source = part.strip()
        if not source:
            continue
        cell_type = "code" if number % 2 else "markdown"
        if cell_type == "markdown":
            # Keep the walkthrough's links usable in Jupyter's heading renderer.
            source = re.sub(
                r"^(#{1,6}) (.+)$",
                lambda match: (
                    '<a id="'
                    + re.sub(r"[^\w\- ]", "", match[2].lower()).replace(" ", "-")
                    + '"></a>\n\n'
                    + match[0]
                ),
                source,
                flags=re.MULTILINE,
            )
        cell = {
            "cell_type": cell_type,
            "id": f"walkthrough-{number:02d}",
            "metadata": {},
            "source": source.splitlines(keepends=True),
        }
        if cell_type == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3.12 (SMB public demo)",
                "language": "python",
                "name": "smb-public-demo",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = (
        Path(__file__).resolve().parents[2] / "public_multimodal_walkthrough.ipynb"
    )
    rendered = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not destination.is_file() or destination.read_text() != rendered:
            raise SystemExit(
                "Notebook is stale. Run examples/public_multimodal/build_notebook.py."
            )
        print("PASS: notebook matches the walkthrough.")
    else:
        destination.write_text(rendered)
        print(destination)
