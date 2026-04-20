"""FastAPI backend for the Knights and Knaves Solver web interface."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
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

_executor = ThreadPoolExecutor(max_workers=4)
_pending: dict[int, asyncio.Future] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

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
# Core solve logic (runs in thread pool)
# ---------------------------------------------------------------------------

def _do_solve(puzzle_id: int) -> dict:
    """Solve a puzzle and persist to cache. Returns the response payload."""
    logic = _load_logic()
    matches = [p for p in logic.get("puzzles", []) if p["id"] == puzzle_id]
    if not matches:
        raise ValueError(f"Puzzle {puzzle_id} not found")
    puzzle = matches[0]
    constraints = puzzle["constraints"]
    people = puzzle["people"]

    # Only compute compact steps here — aris_steps generated lazily on bram download
    _, equiv_steps = build_steps(constraints, compact=True)
    assignments = [
        {person: ("knight" if is_knight else "knave") for person, is_knight in sol.items()}
        for sol in _solve_puzzle(people, constraints)
    ]

    entry = {
        "id": puzzle_id,
        "people": people,
        "equivalence_steps": equiv_steps,
        "assignments": assignments,
        # aris_steps intentionally omitted — generated lazily on first .bram download
    }

    with _cache_lock:
        solutions = _load_solutions()
        if "puzzles" not in solutions:
            solutions["puzzles"] = []
        # Preserve aris_steps if already cached from a prior bram download
        existing = next((p for p in solutions["puzzles"] if p["id"] == puzzle_id), None)
        if existing and "aris_steps" in existing:
            entry["aris_steps"] = existing["aris_steps"]
        solutions["puzzles"] = [p for p in solutions["puzzles"] if p["id"] != puzzle_id]
        solutions["puzzles"].append(entry)
        _save_solutions(solutions)

    sym = _symbol_map(people)
    return {
        "status": "done",
        "id": puzzle_id,
        "people": people,
        "equivalence_steps": equiv_steps,
        "symbol_map": sym,
        "assignments": assignments,
    }


def _precompute_all() -> None:
    """Background task: solve all unsolved puzzles at startup (compact steps only)."""
    logic = _load_logic()
    with _cache_lock:
        solutions = _load_solutions()
        solved_ids = {p["id"] for p in solutions.get("puzzles", []) if "assignments" in p}

    for puzzle in logic.get("puzzles", []):
        if puzzle["id"] not in solved_ids:
            try:
                _do_solve(puzzle["id"])
            except Exception:
                pass  # skip puzzles that fail (e.g. unsupported syntax)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _precompute_all)
    yield


app = FastAPI(title="Knights & Knaves Solver", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/puzzles")
def list_puzzles():
    logic = _load_logic()
    with _cache_lock:
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
async def solve_puzzle_endpoint(puzzle_id: int):
    # Return from cache immediately if available
    with _cache_lock:
        solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)
    if cached and "assignments" in cached:
        sym = _symbol_map(cached["people"])
        return {
            "status": "done",
            "id": cached["id"],
            "people": cached["people"],
            "equivalence_steps": cached["equivalence_steps"],
            "symbol_map": sym,
            "assignments": cached["assignments"],
        }

    # Cached steps exist but assignments missing — compute assignments cheaply via SAT
    if cached and "equivalence_steps" in cached:
        logic = _load_logic()
        puzzle = next((p for p in logic.get("puzzles", []) if p["id"] == puzzle_id), None)
        if puzzle:
            assignments = [
                {person: ("knight" if is_knight else "knave") for person, is_knight in sol.items()}
                for sol in _solve_puzzle(puzzle["people"], puzzle["constraints"])
            ]
            cached["assignments"] = assignments
            with _cache_lock:
                solutions = _load_solutions()
                solutions["puzzles"] = [p for p in solutions["puzzles"] if p["id"] != puzzle_id]
                solutions["puzzles"].append(cached)
                _save_solutions(solutions)
            sym = _symbol_map(cached["people"])
            return {
                "status": "done",
                "id": cached["id"],
                "people": cached["people"],
                "equivalence_steps": cached["equivalence_steps"],
                "symbol_map": sym,
                "assignments": assignments,
            }

    # Verify puzzle exists
    logic = _load_logic()
    if not any(p["id"] == puzzle_id for p in logic.get("puzzles", [])):
        raise HTTPException(status_code=404, detail=f"Puzzle {puzzle_id} not found")

    # If already being solved by precompute or a prior request, report pending
    if puzzle_id in _pending and not _pending[puzzle_id].done():
        return {"status": "pending", "id": puzzle_id}

    # Kick off solve in thread pool
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_executor, _do_solve, puzzle_id)
    _pending[puzzle_id] = future
    return {"status": "pending", "id": puzzle_id}


@app.get("/api/solve/{puzzle_id}/status")
async def solve_status(puzzle_id: int):
    # Check cache first — precompute task may have finished even if our future is still running
    with _cache_lock:
        solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)
    if cached and "assignments" in cached:
        sym = _symbol_map(cached["people"])
        _pending.pop(puzzle_id, None)
        return {
            "status": "done",
            "id": cached["id"],
            "people": cached["people"],
            "equivalence_steps": cached["equivalence_steps"],
            "symbol_map": sym,
            "assignments": cached["assignments"],
        }

    # Check in-flight future
    if puzzle_id in _pending:
        future = _pending[puzzle_id]
        if future.done():
            try:
                result = future.result()
                return result
            except Exception as e:
                return {"status": "error", "detail": str(e)}
        return {"status": "pending", "id": puzzle_id}

    # Fall back to cache
    with _cache_lock:
        solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)
    if cached and "assignments" in cached:
        sym = _symbol_map(cached["people"])
        return {
            "status": "done",
            "id": cached["id"],
            "people": cached["people"],
            "equivalence_steps": cached["equivalence_steps"],
            "symbol_map": sym,
            "assignments": cached["assignments"],
        }

    raise HTTPException(status_code=404, detail=f"Puzzle {puzzle_id} not solved yet")


@app.get("/api/bram/{puzzle_id}")
async def download_bram(puzzle_id: int):
    with _cache_lock:
        solutions = _load_solutions()
    cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)

    # Solve first if not cached at all
    if not cached:
        logic = _load_logic()
        matches = [p for p in logic.get("puzzles", []) if p["id"] == puzzle_id]
        if not matches:
            raise HTTPException(status_code=404, detail=f"Puzzle {puzzle_id} not found")
        loop = asyncio.get_event_loop()
        cached_payload = await loop.run_in_executor(_executor, _do_solve, puzzle_id)
        with _cache_lock:
            solutions = _load_solutions()
        cached = next((p for p in solutions.get("puzzles", []) if p["id"] == puzzle_id), None)

    # Generate aris_steps lazily if missing (first .bram download)
    if "aris_steps" not in cached:
        logic = _load_logic()
        puzzle = next((p for p in logic.get("puzzles", []) if p["id"] == puzzle_id), None)
        if puzzle:
            loop = asyncio.get_event_loop()
            _, aris_steps = await loop.run_in_executor(
                _executor, lambda: build_steps(puzzle["constraints"], compact=False)
            )
            cached["aris_steps"] = aris_steps
            with _cache_lock:
                solutions = _load_solutions()
                solutions["puzzles"] = [p for p in solutions["puzzles"] if p["id"] != puzzle_id]
                solutions["puzzles"].append(cached)
                _save_solutions(solutions)

    xml_text = _build_bram_xml(cached)
    return Response(
        content=xml_text.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="puzzle_{puzzle_id}.bram"'},
    )
