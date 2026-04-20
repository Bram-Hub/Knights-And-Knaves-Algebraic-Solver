#!/usr/bin/env python3
"""Convert Knights and Knaves markdown puzzles into boolean logic JSON."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ParseError(Exception):
    text: str

    def __str__(self) -> str:
        return f"Unsupported statement pattern: {self.text}"


def atom(person: str) -> dict[str, Any]:
    return {"op": "knight", "person": person}


def mk(op: str, *args: Any) -> dict[str, Any]:
    return {"op": op, "args": list(args)}


def implies(a: Any, b: Any) -> dict[str, Any]:
    return mk("or", mk("not", a), b)


def negate(expr: dict[str, Any]) -> dict[str, Any]:
    if expr["op"] == "not":
        return expr["args"][0]
    return mk("not", expr)


def normalize_text(text: str) -> str:
    s = text.strip()
    s = s.strip("'\"")
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".")
    # Normalize common contractions / phrasing variants.
    s = re.sub(r"^that ", "", s, flags=re.I)
    s = re.sub(r"^it is false that ", "it's false that ", s, flags=re.I)
    s = re.sub(r"^it is not the case that ", "it's not the case that ", s, flags=re.I)
    return s


def split_top_level(text: str, sep: str) -> list[str]:
    # No explicit parentheses in source; separator safety is lexical.
    parts: list[str] = []
    marker = f" {sep} "
    idx = text.lower().find(marker)
    while idx != -1:
        left = text[:idx].strip()
        text = text[idx + len(marker) :].strip()
        parts.append(left)
        idx = text.lower().find(marker)
    parts.append(text.strip())
    return [p for p in parts if p]


def parse_person(token: str, speaker: str, names: set[str]) -> str:
    t = token.strip().strip("'\"")
    if t.lower() == "i":
        return speaker
    if t in names:
        return t
    raise ParseError(f"Unknown person token '{token}' for speaker {speaker}")


def parse_predicate_clause(text: str, speaker: str, names: set[str]) -> dict[str, Any]:
    s = normalize_text(text)

    # Negation wrappers.
    for prefix in ("it's false that ", "it's not the case that ", "it's not true that "):
        if s.lower().startswith(prefix):
            inner = s[len(prefix) :]
            return mk("not", parse_expr(inner, speaker, names))

    # Modal / meta speech forms.
    m = re.fullmatch(
        r"(Only a knave would (?:say|claim|tell you) that) (.+)",
        s,
        flags=re.I,
    )
    if m:
        inner = parse_expr(m.group(2), speaker, names)
        # Generic "only a knave would say P" is true exactly when P is false.
        return negate(inner)

    m = re.fullmatch(
        r"([A-Za-z]+|I) (could|would) (?:say|claim|tell you) that (.+)",
        s,
        flags=re.I,
    )
    if m:
        who = parse_person(m.group(1), speaker, names)
        inner = parse_expr(m.group(3), speaker, names)
        # could/would say P in this setting => can utter a truth-status-matching sentence
        return mk("eq", atom(who), inner)

    # Knowledge phrasing. We assume "know that" content proposition is asserted directly.
    m = re.fullmatch(r"([A-Za-z]+|I) know that (.+)", s, flags=re.I)
    if m:
        remainder = m.group(2)
        return parse_expr(remainder, speaker, names)

    # Quantified sentence templates.
    m = re.fullmatch(
        r"At least one of the following is true: that (.+) or that (.+)",
        s,
        flags=re.I,
    )
    if m:
        return mk(
            "or",
            parse_expr(m.group(1), speaker, names),
            parse_expr(m.group(2), speaker, names),
        )

    m = re.fullmatch(r"Of ([A-Za-z]+|I) and ([A-Za-z]+|I), exactly one is a knight", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("not", mk("eq", a, b))

    # Same / different / paired truth-value templates.
    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are the same", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("eq", a, b)

    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are (?:different|not the same)", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("not", mk("eq", a, b))

    m = re.fullmatch(
        r"([A-Za-z]+|I) and ([A-Za-z]+|I) are both knights or both knaves",
        s,
        flags=re.I,
    )
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("eq", a, b)

    # Collective classifications.
    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are knights", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", a, b)

    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are both knights", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", a, b)

    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are knaves", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", mk("not", a), mk("not", b))

    m = re.fullmatch(r"([A-Za-z]+|I) and ([A-Za-z]+|I) are both knaves", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", mk("not", a), mk("not", b))

    m = re.fullmatch(r"both ([A-Za-z]+|I) and ([A-Za-z]+|I) are knaves", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", mk("not", a), mk("not", b))

    m = re.fullmatch(r"both ([A-Za-z]+|I) and ([A-Za-z]+|I) are knights", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", a, b)

    m = re.fullmatch(r"Neither ([A-Za-z]+|I) nor ([A-Za-z]+|I) are knaves", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", a, b)

    m = re.fullmatch(r"Neither ([A-Za-z]+|I) nor ([A-Za-z]+|I) are knights", s, flags=re.I)
    if m:
        a = atom(parse_person(m.group(1), speaker, names))
        b = atom(parse_person(m.group(2), speaker, names))
        return mk("and", mk("not", a), mk("not", b))

    # Direct atomic predicates.
    m = re.fullmatch(r"([A-Za-z]+|I) is a knight", s, flags=re.I)
    if m:
        return atom(parse_person(m.group(1), speaker, names))

    m = re.fullmatch(r"([A-Za-z]+|I) is a knave", s, flags=re.I)
    if m:
        return mk("not", atom(parse_person(m.group(1), speaker, names)))

    m = re.fullmatch(r"([A-Za-z]+|I) am a knight", s, flags=re.I)
    if m:
        return atom(parse_person(m.group(1), speaker, names))

    m = re.fullmatch(r"([A-Za-z]+|I) am a knave", s, flags=re.I)
    if m:
        return mk("not", atom(parse_person(m.group(1), speaker, names)))

    # Pair-wise "both X and Y" constructions where X/Y are full predicates.
    m = re.fullmatch(r"Both (.+) and (.+)", s, flags=re.I)
    if m:
        return mk(
            "and",
            parse_expr(m.group(1), speaker, names),
            parse_expr(m.group(2), speaker, names),
        )

    raise ParseError(s)


def parse_expr(text: str, speaker: str, names: set[str]) -> dict[str, Any]:
    s = normalize_text(text)

    # Canonical either/or before generic OR splitting.
    m = re.fullmatch(r"Either (.+) or (.+)", s, flags=re.I)
    if m:
        return mk(
            "or",
            parse_expr(m.group(1), speaker, names),
            parse_expr(m.group(2), speaker, names),
        )

    # Prefer specific templates before generic conjunction/disjunction splitting.
    try:
        return parse_predicate_clause(s, speaker, names)
    except ParseError:
        pass

    # Generic disjunction/conjunction fallback.
    lower = s.lower()
    if " or " in lower:
        parts = split_top_level(s, "or")
        if len(parts) > 1:
            expr = parse_expr(parts[0], speaker, names)
            for p in parts[1:]:
                expr = mk("or", expr, parse_expr(p, speaker, names))
            return expr

    if " and " in lower:
        parts = split_top_level(s, "and")
        if len(parts) > 1:
            expr = parse_expr(parts[0], speaker, names)
            for p in parts[1:]:
                expr = mk("and", expr, parse_expr(p, speaker, names))
            return expr

    return parse_predicate_clause(s, speaker, names)


def parse_meeting_sentence(sentence: str) -> list[str]:
    m = re.match(r"You meet \w+ inhabitants: (.+)\.$", sentence)
    if not m:
        raise ParseError(f"Could not parse inhabitants sentence: {sentence}")
    people = m.group(1).replace(" and ", ", ")
    names = [p.strip() for p in people.split(",") if p.strip()]
    return names


def parse_statement_sentence(sentence: str, names: set[str]) -> tuple[str, str]:
    # Normalize trailing quote/punctuation artifacts.
    s = sentence.strip()
    s = s.rstrip()
    s = re.sub(r"\s+", " ", s)

    m = re.match(
        r"^([A-Za-z]+)\s+(?:says|said|tells you|told you|claims|claimed)\s*,?\s*(?:that\s+)?(.+?)\.?$",
        s,
        flags=re.I,
    )
    if not m:
        raise ParseError(f"Could not parse statement sentence: {sentence}")

    speaker = m.group(1)
    if speaker not in names:
        raise ParseError(f"Unknown speaker '{speaker}' in sentence: {sentence}")
    statement = normalize_text(m.group(2))
    return speaker, statement


def split_sentences(block_text: str) -> list[str]:
    # Source uses two spaces between sentences. We keep punctuation-based fallback too.
    rough = [s.strip() for s in re.split(r"\s{2,}", block_text.strip()) if s.strip()]
    if len(rough) > 1:
        return rough

    # Fallback tokenizer.
    chunks = re.split(r"(?<=[.?!])\s+(?=[A-Z])", block_text.strip())
    return [c.strip() for c in chunks if c.strip()]


def parse_puzzle_block(puzzle_id: int, text: str) -> dict[str, Any]:
    sentences = split_sentences(text)
    if not sentences:
        raise ParseError(f"Empty puzzle block: {puzzle_id}")

    names = parse_meeting_sentence(sentences[0].rstrip())
    names_set = set(names)

    utterances: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for sentence in sentences[1:]:
        try:
            speaker, raw_statement = parse_statement_sentence(sentence.rstrip("."), names_set)
            expr = parse_expr(raw_statement, speaker, names_set)
            utterances.append(
                {
                    "speaker": speaker,
                    "raw": raw_statement,
                    "formula": expr,
                }
            )
            constraints.append(mk("eq", atom(speaker), expr))
        except ParseError as exc:
            errors.append({"sentence": sentence, "error": str(exc)})

    return {
        "id": puzzle_id,
        "people": names,
        "utterances": utterances,
        "constraints": constraints,
        "unsupported": errors,
    }


def parse_markdown_puzzles(md_text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"^###\s+(\d+)\s*\n(.*?)(?=^###\s+\d+\s*\n|\Z)", re.M | re.S)
    puzzles: list[tuple[int, str]] = []
    for m in pattern.finditer(md_text):
        pid = int(m.group(1))
        block = m.group(2).strip()
        puzzles.append((pid, block))
    return puzzles


def convert_file(input_path: Path) -> dict[str, Any]:
    text = input_path.read_text(encoding="utf-8")
    parsed = parse_markdown_puzzles(text)

    puzzle_objs = [parse_puzzle_block(pid, block) for pid, block in parsed]

    unsupported_total = sum(len(p["unsupported"]) for p in puzzle_objs)
    utterance_total = sum(len(p["utterances"]) + len(p["unsupported"]) for p in puzzle_objs)

    return {
        "source": str(input_path),
        "puzzle_count": len(puzzle_objs),
        "utterance_count": utterance_total,
        "unsupported_count": unsupported_total,
        "logic_language": {
            "variables": "knight(Person)",
            "operators": ["not", "and", "or", "eq"],
            "constraint_rule": "For each utterance U by speaker S: eq(knight(S), U)",
            "notes": [
                "could/would say/claim/tell that P is encoded as eq(knight(X), P)",
                "Only a knave would say that P is encoded as not(P)",
                "'know that ...' is treated as asserting the embedded proposition",
            ],
        },
        "puzzles": puzzle_objs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/Knights and Knaves.md"),
        help="Path to Knights and Knaves markdown file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/knights_and_knaves_logic.json"),
        help="Path for emitted logic JSON",
    )
    args = parser.parse_args()

    result = convert_file(args.input)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Wrote {args.output}")
    print(
        f"Parsed {result['puzzle_count']} puzzles, "
        f"{result['utterance_count']} utterances, "
        f"{result['unsupported_count']} unsupported statements"
    )


if __name__ == "__main__":
    main()
