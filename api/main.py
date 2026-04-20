"""FastAPI backend for the Knights and Knaves Solver web interface."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from solve_knights_knaves import build_steps, solve_puzzle as _solve_puzzle  # noqa: E402

LOGIC_PATH = ROOT / "data" / "knights_and_knaves_logic.json"
SOLUTIONS_PATH = ROOT / "data" / "knights_and_knaves_solutions.json"
ARIS_VERSION = "0.1.0"

app = FastAPI(title="Knights & Knaves Solver")


def _load_logic() -> dict:
    return json.loads(LOGIC_PATH.read_text(encoding="utf-8"))


def _load_solutions() -> dict:
    if not SOLUTIONS_PATH.exists():
        return {"puzzles": []}
    return json.loads(SOLUTIONS_PATH.read_text(encoding="utf-8"))


def _save_solutions(data: dict) -> None:
    SOLUTIONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _build_bram_xml(puzzle: dict) -> str:
    steps = puzzle.get("aris_steps") or puzzle["equivalence_steps"]
    people = puzzle["people"]
    symbol_map = _symbol_map(people)
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
    ET.SubElement(assumption, "raw").text = _remap(steps[0]["formula"], symbol_map)

    prev_line = linenum
    for step in steps[1:]:
        linenum += 1
        step_el = ET.SubElement(proof, "step", {"linenum": str(linenum)})
        ET.SubElement(step_el, "raw").text = _remap(step["formula"], symbol_map)
        ET.SubElement(step_el, "rule").text = step["rule"]
        premise_ref = step.get("premise", prev_line)
        if premise_ref is not None:
            ET.SubElement(step_el, "premise").text = str(premise_ref)
        prev_line = linenum

    final_formula = _remap(steps[-1]["formula"], symbol_map)
    goal_el = ET.SubElement(proof, "goal")
    ET.SubElement(goal_el, "raw").text = final_formula

    _indent(root)
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + body + "\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/puzzles")
def list_puzzles():
    logic = _load_logic()
    solutions = _load_solutions()
    solved_ids = {p["id"] for p in solutions.get("puzzles", [])}

    result = []
    for puzzle in logic.get("puzzles", []):
        result.append(
            {
                "id": puzzle["id"],
                "people": puzzle["people"],
                "utterances": [
                    {"speaker": u["speaker"], "raw": u["raw"]}
                    for u in puzzle.get("utterances", [])
                ],
                "solved": puzzle["id"] in solved_ids,
            }
        )
    return result


@app.post("/api/solve/{puzzle_id}")
def solve_puzzle(puzzle_id: int):
    logic = _load_logic()
    matches = [p for p in logic.get("puzzles", []) if p["id"] == puzzle_id]
    if not matches:
        raise HTTPException(status_code=404, detail=f"Puzzle {puzzle_id} not found")
    puzzle = matches[0]

    solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)
    if cached and "assignments" in cached:
        sym = _symbol_map(cached["people"])
        return {
            "id": cached["id"],
            "people": cached["people"],
            "equivalence_steps": cached["equivalence_steps"],
            "symbol_map": sym,
            "assignments": cached["assignments"],
        }

    constraints = puzzle["constraints"]
    people = puzzle["people"]
    _, equiv_steps = build_steps(constraints, compact=True)
    _, aris_steps = build_steps(constraints, compact=False)
    assignments = [
        {person: ("knight" if is_knight else "knave") for person, is_knight in sol.items()}
        for sol in _solve_puzzle(people, constraints)
    ]

    entry = {
        "id": puzzle_id,
        "people": people,
        "equivalence_steps": equiv_steps,
        "aris_steps": aris_steps,
        "assignments": assignments,
    }
    if "puzzles" not in solutions:
        solutions["puzzles"] = []
    # Replace existing entry if present (e.g. cache missing assignments field)
    solutions["puzzles"] = [p for p in solutions["puzzles"] if p["id"] != puzzle_id]
    solutions["puzzles"].append(entry)
    _save_solutions(solutions)

    sym = _symbol_map(people)
    return {
        "id": puzzle_id,
        "people": people,
        "equivalence_steps": equiv_steps,
        "symbol_map": sym,
        "assignments": assignments,
    }


@app.get("/api/bram/{puzzle_id}")
def download_bram(puzzle_id: int):
    solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)

    if not cached:
        logic = _load_logic()
        matches = [p for p in logic.get("puzzles", []) if p["id"] == puzzle_id]
        if not matches:
            raise HTTPException(status_code=404, detail=f"Puzzle {puzzle_id} not found")
        puzzle = matches[0]
        constraints = puzzle["constraints"]
        people = puzzle["people"]
        _, equiv_steps = build_steps(constraints, compact=True)
        _, aris_steps = build_steps(constraints, compact=False)
        cached = {
            "id": puzzle_id,
            "people": people,
            "equivalence_steps": equiv_steps,
            "aris_steps": aris_steps,
        }
        if "puzzles" not in solutions:
            solutions["puzzles"] = []
        solutions["puzzles"].append(cached)
        _save_solutions(solutions)

    xml_text = _build_bram_xml(cached)
    return Response(
        content=xml_text.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="puzzle_{puzzle_id}.bram"'},
    )
