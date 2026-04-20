"""Pre-generate static JSON and .bram files for the first N puzzles.

Outputs to web/public/data/:
  puzzles.json          — puzzle list (id, people, utterances, solved)
  solutions/{id}.json   — per-puzzle solution + proof steps
  bram/{id}.bram        — Aris-compatible proof file

Usage:
  python3 scripts/pregenerate.py            # generate all 100 (for Vercel)
  python3 scripts/pregenerate.py --limit 10 # quick local dev run
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from solve_knights_knaves import build_steps, solve_puzzle  # noqa: E402

LOGIC_PATH = ROOT / "data" / "knights_and_knaves_logic.json"
OUT_DIR = ROOT / "web" / "public" / "data"
ARIS_VERSION = "0.1.0"
PUZZLE_LIMIT = 100


def _letter_for_index(idx: int) -> str:
    out = ""
    n = idx
    while True:
        n, r = divmod(n, 26)
        out = chr(ord("A") + r) + out
        if n == 0:
            break
        n -= 1
    return out


def _symbol_map(people: list[str]) -> dict[str, str]:
    return {p: _letter_for_index(i) for i, p in enumerate(people)}


def _remap(formula: str, symbol_map: dict[str, str]) -> str:
    mapped = formula
    for person in sorted(symbol_map.keys(), key=len, reverse=True):
        mapped = mapped.replace(f"K_{person}", symbol_map[person])
    return mapped


def _indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def _build_bram_xml(puzzle: dict, steps: list, sym: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    root = ET.Element("bram")
    ET.SubElement(root, "program").text = "Aris"
    ET.SubElement(root, "version").text = ARIS_VERSION

    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "author").text = "mikehalpern"
    ET.SubElement(metadata, "created").text = now
    ET.SubElement(metadata, "modified").text = now
    hash_input = json.dumps(puzzle, sort_keys=True).encode("utf-8")
    ET.SubElement(metadata, "hash").text = base64.b64encode(
        hashlib.sha256(hash_input).digest()
    ).decode("ascii")

    proof = ET.SubElement(root, "proof", {"id": "0"})

    linenum = 0
    assumption = ET.SubElement(proof, "assumption", {"linenum": str(linenum)})
    ET.SubElement(assumption, "raw").text = _remap(steps[0]["formula"], sym)

    prev_line = linenum
    for step in steps[1:]:
        linenum += 1
        step_el = ET.SubElement(proof, "step", {"linenum": str(linenum)})
        ET.SubElement(step_el, "raw").text = _remap(step["formula"], sym)
        ET.SubElement(step_el, "rule").text = step["rule"]
        premise_ref = step.get("premise", prev_line)
        if premise_ref is not None:
            ET.SubElement(step_el, "premise").text = str(premise_ref)
        prev_line = linenum

    final_formula = _remap(steps[-1]["formula"], sym)
    goal_el = ET.SubElement(proof, "goal")
    ET.SubElement(goal_el, "raw").text = final_formula

    _indent(root)
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + body + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=PUZZLE_LIMIT,
                        help="Number of puzzles to generate (default: 100)")
    parser.add_argument("--no-bram", action="store_true",
                        help="Skip .bram file generation (saves ~100 MB for Vercel)")
    args = parser.parse_args()

    logic = json.loads(LOGIC_PATH.read_text(encoding="utf-8"))
    puzzles = logic["puzzles"][:args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "solutions").mkdir(exist_ok=True)
    if not args.no_bram:
        (OUT_DIR / "bram").mkdir(exist_ok=True)

    puzzle_list = []

    for i, puzzle in enumerate(puzzles):
        pid = puzzle["id"]
        print(f"[{i+1:3d}/{len(puzzles)}] Puzzle {pid} ({', '.join(puzzle['people'])})…", end=" ", flush=True)
        try:
            constraints = puzzle["constraints"]
            people = puzzle["people"]

            _, steps = build_steps(constraints)
            assignments = [
                {person: ("knight" if is_knight else "knave") for person, is_knight in sol.items()}
                for sol in solve_puzzle(people, constraints)
            ]
            sym = _symbol_map(people)

            solution = {
                "id": pid,
                "people": people,
                "equivalence_steps": steps,
                "symbol_map": sym,
                "assignments": assignments,
            }
            (OUT_DIR / "solutions" / f"{pid}.json").write_text(
                json.dumps(solution, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if not args.no_bram:
                bram_xml = _build_bram_xml(puzzle, steps, sym)
                (OUT_DIR / "bram" / f"{pid}.bram").write_text(bram_xml, encoding="utf-8")

            puzzle_list.append({
                "id": pid,
                "people": people,
                "utterances": [
                    {"speaker": u["speaker"], "raw": u["raw"]}
                    for u in puzzle.get("utterances", [])
                ],
                "solved": True,
            })
            print("ok")
        except Exception as e:
            print(f"FAILED — {e}")
            puzzle_list.append({
                "id": pid,
                "people": puzzle["people"],
                "utterances": [
                    {"speaker": u["speaker"], "raw": u["raw"]}
                    for u in puzzle.get("utterances", [])
                ],
                "solved": False,
            })

    (OUT_DIR / "puzzles.json").write_text(
        json.dumps(puzzle_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    solved = sum(1 for p in puzzle_list if p["solved"])
    print(f"\nDone — {solved}/{len(puzzles)} puzzles pre-generated → {OUT_DIR}")


if __name__ == "__main__":
    main()
