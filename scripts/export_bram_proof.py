#!/usr/bin/env python3
"""Export a single puzzle proof to Bram (.bram) XML format."""

from __future__ import annotations

import argparse
import hashlib
import base64
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.solve_knights_knaves import validate_proof_steps


def indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def letter_for_index(idx: int) -> str:
    # A, B, ..., Z, AA, AB, ...
    out = ""
    n = idx
    while True:
        n, r = divmod(n, 26)
        out = chr(ord("A") + r) + out
        if n == 0:
            break
        n -= 1
    return out


def build_symbol_map(people_order: list[str]) -> dict[str, str]:
    return {person: letter_for_index(i) for i, person in enumerate(people_order)}


def remap_formula_text(formula: str, symbol_map: dict[str, str]) -> str:
    mapped = formula
    # Replace longer names first to avoid partial overlaps.
    for person in sorted(symbol_map.keys(), key=len, reverse=True):
        mapped = mapped.replace(f"K_{person}", symbol_map[person])
    return mapped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("problem", type=int, help="Puzzle number to export")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/knights_and_knaves_solutions.json"),
        help="Solved puzzles JSON path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .bram file path (default: data/bram/puzzle_<id>.bram)",
    )
    parser.add_argument(
        "--author",
        type=str,
        default="mikehalpern",
        help="Author metadata for .bram file",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"Missing {args.input}. Run: python3 scripts/solve_knights_knaves.py"
        )

    data = json.loads(args.input.read_text(encoding="utf-8"))
    matches = [p for p in data.get("puzzles", []) if p.get("id") == args.problem]
    if not matches:
        raise SystemExit(f"Puzzle {args.problem} not found in {args.input}")
    puzzle = matches[0]
    valid, error = validate_proof_steps(puzzle["equivalence_steps"])
    if not valid:
        raise SystemExit(f"Refusing to export invalid ARIS proof for puzzle {args.problem}: {error}")
    symbol_map = build_symbol_map(puzzle["people"])

    output_path = args.output or Path(f"data/bram/puzzle_{args.problem}.bram")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("bram")
    program = ET.SubElement(root, "program")
    program.text = "Aris"
    version = ET.SubElement(root, "version")
    version.text = "0.1.0"

    metadata = ET.SubElement(root, "metadata")
    author = ET.SubElement(metadata, "author")
    author.text = "ARIS-YEW-UI"
    hash_el = ET.SubElement(metadata, "hash")
    hash_input = json.dumps(puzzle, sort_keys=True).encode("utf-8")
    hash_el.text = base64.b64encode(hashlib.sha256(hash_input).digest()).decode("ascii")

    proof = ET.SubElement(root, "proof", {"id": "0"})

    linenum = 0
    assumption = ET.SubElement(proof, "assumption", {"linenum": str(linenum)})
    a_raw = ET.SubElement(assumption, "raw")
    a_raw.text = remap_formula_text(puzzle["equivalence_steps"][0]["formula"], symbol_map)

    prev_line = linenum
    for step in puzzle["equivalence_steps"][1:]:
        linenum += 1
        step_el = ET.SubElement(proof, "step", {"linenum": str(linenum)})

        s_raw = ET.SubElement(step_el, "raw")
        s_raw.text = remap_formula_text(step["formula"], symbol_map)

        s_rule = ET.SubElement(step_el, "rule")
        s_rule.text = step["rule"]

        premise_ref = step.get("premise", prev_line)
        if premise_ref is not None:
            premise = ET.SubElement(step_el, "premise")
            premise.text = str(premise_ref)
        prev_line = linenum

    indent(root)
    xml_body = ET.tostring(root, encoding="unicode")
    xml_text = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + xml_body + "\n"
    output_path.write_text(xml_text, encoding="utf-8")

    print(f"Wrote {output_path}")
    print("Symbol map:", ", ".join(f"{p}->{s}" for p, s in symbol_map.items()))


if __name__ == "__main__":
    main()
