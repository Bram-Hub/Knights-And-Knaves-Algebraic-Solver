#!/usr/bin/env python3
"""View solutions for a specific Knights and Knaves puzzle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def print_puzzle(puzzle: dict, show_steps: bool) -> None:
    print(f"Puzzle {puzzle['id']}")
    print(f"People: {', '.join(puzzle['people'])}")
    print(f"Solution count: {puzzle['solution_count']}")

    if puzzle.get("solution_literals"):
        for i, rendered in enumerate(puzzle["solution_literals"], start=1):
            print(f"  Solution {i}: {rendered}")
    elif puzzle["solutions"]:
        for i, solution in enumerate(puzzle["solutions"], start=1):
            rendered = ", ".join(f"{name}={status}" for name, status in solution.items())
            print(f"  Solution {i}: {rendered}")
    else:
        print("  No satisfying assignment.")

    if show_steps:
        print("\nEquivalence steps:")
        for i, step in enumerate(puzzle["equivalence_steps"], start=1):
            print(f"  Step {i}: {step['rule']}")
            print(f"    {step['description']}")
            print(f"    {step['formula']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "problem",
        type=int,
        help="Puzzle number to view (e.g., 1)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/knights_and_knaves_solutions.json"),
        help="Path to solved puzzles JSON",
    )
    parser.add_argument(
        "--steps",
        action="store_true",
        help="Also print boolean equivalence steps",
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

    print_puzzle(matches[0], args.steps)


if __name__ == "__main__":
    main()
