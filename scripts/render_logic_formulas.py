#!/usr/bin/env python3
"""Render converted Knights and Knaves logic JSON into readable formulas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def to_formula(expr: dict[str, Any]) -> str:
    op = expr["op"]
    if op == "knight":
        return f"K_{expr['person']}"

    args = expr.get("args", [])
    if op == "not":
        return f"¬({to_formula(args[0])})"
    if op == "and":
        return f"({to_formula(args[0])} ∧ {to_formula(args[1])})"
    if op == "or":
        return f"({to_formula(args[0])} ∨ {to_formula(args[1])})"
    if op == "eq":
        return f"({to_formula(args[0])} ↔ {to_formula(args[1])})"

    raise ValueError(f"Unknown operator: {op}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/knights_and_knaves_logic.json"),
        help="Converted logic JSON path",
    )
    parser.add_argument(
        "--puzzle-id",
        type=int,
        default=None,
        help="If set, only render this puzzle id",
    )
    parser.add_argument(
        "--max-puzzles",
        type=int,
        default=None,
        help="Limit number of puzzles rendered",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    puzzles = data["puzzles"]

    if args.puzzle_id is not None:
        puzzles = [p for p in puzzles if p["id"] == args.puzzle_id]

    if args.max_puzzles is not None:
        puzzles = puzzles[: args.max_puzzles]

    for puzzle in puzzles:
        print(f"Puzzle {puzzle['id']}")
        print(f"People: {', '.join(puzzle['people'])}")
        for idx, utt in enumerate(puzzle["utterances"], start=1):
            speaker = utt["speaker"]
            raw = utt["raw"]
            formula = to_formula(utt["formula"])
            constraint = to_formula(puzzle["constraints"][idx - 1])
            print(f"  {idx}. {speaker}: \"{raw}\"")
            print(f"     U{idx} = {formula}")
            print(f"     C{idx}: {constraint}")
        print()


if __name__ == "__main__":
    main()
