#!/usr/bin/env python3
"""Solve Knights and Knaves puzzles and emit DNF-first boolean-equivalence steps."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import deque
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

Expr = dict[str, Any]
Step = dict[str, str]


def mk(op: str, *args: Expr) -> Expr:
    return {"op": op, "args": list(args)}


def atom(person: str) -> Expr:
    return {"op": "knight", "person": person}


def expr_to_str(expr: Expr) -> str:
    def wrap(child: Expr) -> str:
        if child["op"] == "knight":
            return expr_to_str(child)
        if child["op"] == "not" and child["args"][0]["op"] == "knight":
            return expr_to_str(child)
        return f"({expr_to_str(child)})"

    op = expr["op"]
    if op == "knight":
        return f"K_{expr['person']}"
    if op == "not":
        return f"¬{wrap(expr['args'][0])}"
    if op == "and":
        return f"({expr_to_str(expr['args'][0])} ∧ {expr_to_str(expr['args'][1])})"
    if op == "or":
        return f"({expr_to_str(expr['args'][0])} ∨ {expr_to_str(expr['args'][1])})"
    if op == "eq":
        return f"({expr_to_str(expr['args'][0])} ↔ {expr_to_str(expr['args'][1])})"
    if op in {"true", "false"}:
        return "⊤" if op == "true" else "⊥"
    raise ValueError(f"Unknown op: {op}")


def eval_expr(expr: Expr, assignment: dict[str, bool]) -> bool:
    op = expr["op"]
    if op == "knight":
        return assignment[expr["person"]]
    if op == "true":
        return True
    if op == "false":
        return False

    args = expr["args"]
    if op == "not":
        return not eval_expr(args[0], assignment)
    if op == "and":
        return eval_expr(args[0], assignment) and eval_expr(args[1], assignment)
    if op == "or":
        return eval_expr(args[0], assignment) or eval_expr(args[1], assignment)
    if op == "eq":
        return eval_expr(args[0], assignment) == eval_expr(args[1], assignment)

    raise ValueError(f"Unknown op: {op}")


def make_and(items: list[Expr]) -> Expr:
    flat: list[Expr] = []
    for item in items:
        if item["op"] == "and":
            flat.extend(flatten_and(item))
        else:
            flat.append(deepcopy(item))
    if not flat:
        return {"op": "true", "args": []}
    out = flat[0]
    for item in flat[1:]:
        out = mk("and", out, item)
    return out


def make_or(items: list[Expr]) -> Expr:
    flat: list[Expr] = []
    for item in items:
        if item["op"] == "or":
            flat.extend(flatten_or(item))
        else:
            flat.append(deepcopy(item))
    if not flat:
        return {"op": "false", "args": []}
    out = flat[0]
    for item in flat[1:]:
        out = mk("or", out, item)
    return out


def flatten_and(expr: Expr) -> list[Expr]:
    if expr["op"] != "and":
        return [deepcopy(expr)]
    return flatten_and(expr["args"][0]) + flatten_and(expr["args"][1])


def flatten_or(expr: Expr) -> list[Expr]:
    if expr["op"] != "or":
        return [deepcopy(expr)]
    return flatten_or(expr["args"][0]) + flatten_or(expr["args"][1])


def reassociate(expr: Expr) -> Expr:
    op = expr["op"]
    if op == "and":
        return make_and([reassociate(item) for item in flatten_and(expr)])
    if op == "or":
        return make_or([reassociate(item) for item in flatten_or(expr)])
    if op == "not":
        return mk("not", reassociate(expr["args"][0]))
    if op in {"knight", "true", "false"}:
        return deepcopy(expr)
    return {"op": op, "args": [reassociate(arg) for arg in expr.get("args", [])]}


def is_literal(expr: Expr) -> bool:
    return expr["op"] == "knight" or (
        expr["op"] == "not" and expr["args"][0]["op"] == "knight"
    )


def literal_key(expr: Expr) -> tuple[str, str, str]:
    if expr["op"] == "knight":
        return ("lit", expr["person"], "pos")
    if expr["op"] == "not" and expr["args"][0]["op"] == "knight":
        return ("lit", expr["args"][0]["person"], "neg")
    if expr["op"] == "true":
        return ("const", "true", "")
    if expr["op"] == "false":
        return ("const", "false", "")
    raise ValueError(f"Not a literal: {expr}")


def expr_sort_key(expr: Expr) -> tuple[Any, ...]:
    op = expr["op"]
    if op == "knight":
        return (0, expr["person"])
    if op == "not" and expr["args"][0]["op"] == "knight":
        return (1, expr["args"][0]["person"])
    if op == "false":
        return (2,)
    if op == "true":
        return (3,)
    if op == "and":
        return (4, tuple(expr_sort_key(item) for item in flatten_and(expr)))
    if op == "or":
        return (5, tuple(expr_sort_key(item) for item in flatten_or(expr)))
    if op == "eq":
        return (6, tuple(expr_sort_key(item) for item in expr["args"]))
    return (7, expr_to_str(expr))


def term_signature(term: Expr) -> tuple[tuple[Any, ...], ...]:
    return tuple(expr_sort_key(item) for item in flatten_and(term))


def is_negation_pair(a: Expr, b: Expr) -> bool:
    return (a["op"] == "not" and a["args"][0] == b) or (
        b["op"] == "not" and b["args"][0] == a
    )


def is_dnf_term(expr: Expr) -> bool:
    op = expr["op"]
    if is_literal(expr) or op in {"true", "false"}:
        return True
    if op != "and":
        return False
    return all(is_literal(item) or item["op"] in {"true", "false"} for item in flatten_and(expr))


def is_dnf(expr: Expr) -> bool:
    op = expr["op"]
    if is_dnf_term(expr):
        return True
    if op != "or":
        return False
    return all(is_dnf_term(item) for item in flatten_or(expr))


def gather_people(expr: Expr) -> set[str]:
    op = expr["op"]
    if op == "knight":
        return {expr["person"]}
    people: set[str] = set()
    for arg in expr.get("args", []):
        people |= gather_people(arg)
    return people


def rewrite_once(expr: Expr, rule_fn: Any) -> tuple[Expr, bool]:
    rewritten = rule_fn(expr)
    if rewritten is not None:
        return rewritten, True

    op = expr["op"]
    if op in {"knight", "true", "false"}:
        return expr, False
    if op == "not":
        child, changed = rewrite_once(expr["args"][0], rule_fn)
        if changed:
            return mk("not", child), True
        return expr, False

    left, changed = rewrite_once(expr["args"][0], rule_fn)
    if changed:
        return {"op": op, "args": [left, expr["args"][1]]}, True
    right, changed = rewrite_once(expr["args"][1], rule_fn)
    if changed:
        return {"op": op, "args": [expr["args"][0], right]}, True
    return expr, False


def apply_rule_until_fixed(
    expr: Expr, rule_name: str, description: str, rule_fn: Any, max_iterations: int = 1024
) -> tuple[Expr, list[Step]]:
    current = deepcopy(expr)
    steps: list[Step] = []
    for _ in range(max_iterations):
        updated, changed = rewrite_once(current, rule_fn)
        if not changed:
            break
        current = updated
        steps.append(
            {
                "rule": rule_name,
                "description": description,
                "formula": expr_to_str(current),
            }
        )
    return current, steps


def maybe_add_step(
    steps: list[Step], current: Expr, updated: Expr, rule: str, description: str
) -> Expr:
    if updated != current:
        steps.append(
            {
                "rule": rule,
                "description": description,
                "formula": expr_to_str(updated),
            }
        )
    return updated


def add_step(steps: list[Step], rule: str, description: str, expr: Expr) -> None:
    steps.append(
        {
            "rule": rule,
            "description": description,
            "formula": expr_to_str(expr),
        }
    )


def rule_biconditional_equivalence(expr: Expr) -> Expr | None:
    if expr["op"] != "eq":
        return None
    left, right = expr["args"]
    return mk(
        "or",
        mk("and", deepcopy(left), deepcopy(right)),
        mk("and", mk("not", deepcopy(left)), mk("not", deepcopy(right))),
    )


def rule_double_negation(expr: Expr) -> Expr | None:
    if expr["op"] == "not" and expr["args"][0]["op"] == "not":
        return deepcopy(expr["args"][0]["args"][0])
    return None


def rule_demorgan(expr: Expr) -> Expr | None:
    if expr["op"] != "not":
        return None
    inner = expr["args"][0]
    if inner["op"] == "and":
        return mk(
            "or",
            mk("not", deepcopy(inner["args"][0])),
            mk("not", deepcopy(inner["args"][1])),
        )
    if inner["op"] == "or":
        return mk(
            "and",
            mk("not", deepcopy(inner["args"][0])),
            mk("not", deepcopy(inner["args"][1])),
        )
    if inner["op"] == "true":
        return {"op": "false", "args": []}
    if inner["op"] == "false":
        return {"op": "true", "args": []}
    return None


def rule_inverse(expr: Expr) -> Expr | None:
    if expr["op"] != "not":
        return None
    inner = expr["args"][0]
    if inner["op"] == "true":
        return {"op": "false", "args": []}
    if inner["op"] == "false":
        return {"op": "true", "args": []}
    return None


def rule_distribution_dnf(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if right["op"] != "or":
            return None
        return mk(
            "or",
            mk("and", deepcopy(left), deepcopy(right["args"][0])),
            mk("and", deepcopy(left), deepcopy(right["args"][1])),
        )
    return None


def rule_association(expr: Expr) -> Expr | None:
    if expr["op"] not in {"and", "or"}:
        return None
    left, right = expr["args"]
    if left["op"] == expr["op"]:
        return mk(
            expr["op"],
            deepcopy(left["args"][0]),
            mk(expr["op"], deepcopy(left["args"][1]), deepcopy(right)),
        )
    if right["op"] == expr["op"]:
        return mk(
            expr["op"],
            mk(expr["op"], deepcopy(left), deepcopy(right["args"][0])),
            deepcopy(right["args"][1]),
        )
    return None


def rule_commutation(expr: Expr) -> Expr | None:
    if expr["op"] not in {"and", "or"}:
        return None
    left, right = expr["args"]

    def comm_key(item: Expr) -> tuple[Any, ...]:
        if item["op"] == "not" and item["args"][0]["op"] == "knight":
            return (0, item["args"][0]["person"])
        if item["op"] == "knight":
            return (1, item["person"])
        return expr_sort_key(item)

    if comm_key(left) > comm_key(right):
        return mk(expr["op"], deepcopy(right), deepcopy(left))
    return None


def association_variants(expr: Expr) -> list[Expr]:
    if expr["op"] not in {"and", "or"}:
        return []
    left, right = expr["args"]
    variants: list[Expr] = []
    if left["op"] == expr["op"]:
        variants.append(
            mk(
                expr["op"],
                deepcopy(left["args"][0]),
                mk(expr["op"], deepcopy(left["args"][1]), deepcopy(right)),
            )
        )
    if right["op"] == expr["op"]:
        variants.append(
            mk(
                expr["op"],
                mk(expr["op"], deepcopy(left), deepcopy(right["args"][0])),
                deepcopy(right["args"][1]),
            )
        )
    return variants


def commutation_variant(expr: Expr) -> Expr | None:
    if expr["op"] not in {"and", "or"}:
        return None
    left, right = expr["args"]
    if left == right:
        return None
    return mk(expr["op"], deepcopy(right), deepcopy(left))


def enumerate_structural_rewrites(
    expr: Expr, local_ops: set[str] | None = None
) -> list[tuple[str, str, Expr]]:
    rewrites: list[tuple[str, str, Expr]] = []

    if local_ops is None or expr["op"] in local_ops:
        for variant in association_variants(expr):
            rewrites.append(("ASSOCIATION", "Regroup conjunctions and disjunctions.", variant))

        swapped = commutation_variant(expr)
        if swapped is not None:
            rewrites.append(
                ("COMMUTATION", "Swap statements within the same level of parentheses.", swapped)
            )

    op = expr["op"]
    if op in {"knight", "true", "false"}:
        return rewrites
    if op == "not":
        for rule_name, description, child_variant in enumerate_structural_rewrites(
            expr["args"][0], local_ops
        ):
            rewrites.append((rule_name, description, mk("not", child_variant)))
        return rewrites

    left, right = expr["args"]
    for rule_name, description, child_variant in enumerate_structural_rewrites(left, local_ops):
        rewrites.append((rule_name, description, {"op": op, "args": [child_variant, deepcopy(right)]}))
    for rule_name, description, child_variant in enumerate_structural_rewrites(right, local_ops):
        rewrites.append((rule_name, description, {"op": op, "args": [deepcopy(left), child_variant]}))
    return rewrites


def count_direct_rule_matches(expr: Expr, rule_fn: Any) -> int:
    count = 1 if rule_fn(expr) is not None else 0
    op = expr["op"]
    if op in {"knight", "true", "false"}:
        return count
    if op == "not":
        return count + count_direct_rule_matches(expr["args"][0], rule_fn)
    return (
        count
        + count_direct_rule_matches(expr["args"][0], rule_fn)
        + count_direct_rule_matches(expr["args"][1], rule_fn)
    )


def structural_fingerprint(expr: Expr) -> tuple[Any, ...]:
    op = expr["op"]
    if op == "knight":
        return ("knight", expr["person"])
    if op in {"true", "false"}:
        return (op,)
    if op == "not":
        return ("not", structural_fingerprint(expr["args"][0]))
    return (op, structural_fingerprint(expr["args"][0]), structural_fingerprint(expr["args"][1]))


def get_subexpr(expr: Expr, path: tuple[int, ...]) -> Expr:
    current = expr
    for index in path:
        current = current["args"][index]
    return current


def replace_subexpr(expr: Expr, path: tuple[int, ...], replacement: Expr) -> Expr:
    if not path:
        return replacement
    op = expr["op"]
    if op == "not":
        return mk("not", replace_subexpr(expr["args"][0], path[1:], replacement))
    args = list(expr["args"])
    args[path[0]] = replace_subexpr(args[path[0]], path[1:], replacement)
    return {"op": op, "args": args}


def disjunct_paths(expr: Expr, path: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    if expr["op"] != "or":
        return [path]
    return disjunct_paths(expr["args"][0], path + (0,)) + disjunct_paths(expr["args"][1], path + (1,))


def conjunct_factor_paths(expr: Expr, path: tuple[int, ...] = ()) -> list[tuple[tuple[int, ...], Expr]]:
    if expr["op"] != "and":
        return [(path, deepcopy(expr))]
    return conjunct_factor_paths(expr["args"][0], path + (0,)) + conjunct_factor_paths(expr["args"][1], path + (1,))


def common_prefix_path(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    out: list[int] = []
    for a, b in zip(left, right):
        if a != b:
            break
        out.append(a)
    return tuple(out)


def term_literals(term: Expr) -> list[Expr]:
    return flatten_and(term)


def term_has_complement(term: Expr) -> bool:
    items = term_literals(term)
    return any(is_negation_pair(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items)))


def term_has_duplicate(term: Expr) -> bool:
    items = term_literals(term)
    return any(items[i] == items[j] for i in range(len(items)) for j in range(i + 1, len(items)))


def term_has_true(term: Expr) -> bool:
    items = term_literals(term)
    return len(items) > 1 and any(item["op"] == "true" for item in items)


def term_has_false(term: Expr) -> bool:
    items = term_literals(term)
    return len(items) > 1 and any(item["op"] == "false" for item in items)


def term_key_set(term: Expr) -> set[tuple[Any, ...]]:
    return {expr_sort_key(item) for item in flatten_and(term)}


def dnf_has_duplicate_terms(expr: Expr) -> bool:
    terms = flatten_or(expr)
    seen: set[tuple[tuple[Any, ...], ...]] = set()
    for term in terms:
        signature = term_signature(term)
        if signature in seen:
            return True
        seen.add(signature)
    return False


def dnf_has_false_term(expr: Expr) -> bool:
    terms = flatten_or(expr)
    return len(terms) > 1 and any(term["op"] == "false" for term in terms)


def dnf_has_true_term(expr: Expr) -> bool:
    terms = flatten_or(expr)
    return len(terms) > 1 and any(term["op"] == "true" for term in terms)


def dnf_has_absorption(expr: Expr) -> bool:
    terms = flatten_or(expr)
    key_sets = [term_key_set(term) for term in terms]
    for i, left_keys in enumerate(key_sets):
        for j, right_keys in enumerate(key_sets):
            if i != j and left_keys < right_keys:
                return True
    return False


def dnf_has_adjacency(expr: Expr) -> bool:
    terms = flatten_or(expr)
    key_sets = [term_key_set(term) for term in terms]
    raw_terms = [flatten_and(term) for term in terms]
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            diff_left = key_sets[i] - key_sets[j]
            diff_right = key_sets[j] - key_sets[i]
            if len(diff_left) != 1 or len(diff_right) != 1:
                continue
            left_item = next(item for item in raw_terms[i] if expr_sort_key(item) in diff_left)
            right_item = next(item for item in raw_terms[j] if expr_sort_key(item) in diff_right)
            if is_negation_pair(left_item, right_item):
                return True
    return False


def distribution_candidate_paths(expr: Expr, path: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    candidates: list[tuple[int, ...]] = []
    op = expr["op"]
    if op == "not":
        return distribution_candidate_paths(expr["args"][0], path + (0,))
    if op in {"and", "or", "eq"}:
        candidates.extend(distribution_candidate_paths(expr["args"][0], path + (0,)))
        candidates.extend(distribution_candidate_paths(expr["args"][1], path + (1,)))
    if op == "and" and any(item["op"] == "or" for item in flatten_and(expr)):
        candidates.append(path)
    return candidates


def connective_candidate_paths(
    expr: Expr,
    target_op: str,
    predicate: Any,
    path: tuple[int, ...] = (),
) -> list[tuple[int, ...]]:
    candidates: list[tuple[int, ...]] = []
    op = expr["op"]
    if op == "not":
        return connective_candidate_paths(expr["args"][0], target_op, predicate, path + (0,))
    if op in {"and", "or", "eq"}:
        candidates.extend(connective_candidate_paths(expr["args"][0], target_op, predicate, path + (0,)))
        candidates.extend(connective_candidate_paths(expr["args"][1], target_op, predicate, path + (1,)))
    if op == target_op and predicate(expr):
        candidates.append(path)
    return candidates


def find_term_rule_path(expr: Expr, kind: str) -> tuple[int, ...] | None:
    for term_path in disjunct_paths(expr):
        term = get_subexpr(expr, term_path)
        if term["op"] != "and":
            continue
        factors = conjunct_factor_paths(term)
        if kind == "complement":
            for i, (left_path, left_expr) in enumerate(factors):
                for right_path, right_expr in factors[i + 1 :]:
                    if is_negation_pair(left_expr, right_expr):
                        return term_path + common_prefix_path(left_path, right_path)
        elif kind == "duplicate":
            for i, (left_path, left_expr) in enumerate(factors):
                for right_path, right_expr in factors[i + 1 :]:
                    if left_expr == right_expr:
                        return term_path + common_prefix_path(left_path, right_path)
        elif kind in {"false", "true"}:
            target_op = kind
            for index, (factor_path, factor_expr) in enumerate(factors):
                if factor_expr["op"] != target_op:
                    continue
                neighbor_index = index - 1 if index > 0 else index + 1
                if 0 <= neighbor_index < len(factors):
                    return term_path + common_prefix_path(factor_path, factors[neighbor_index][0])
    return None


def containing_term_path(expr: Expr, path: tuple[int, ...]) -> tuple[int, ...]:
    term_paths = disjunct_paths(expr)
    matching = [term_path for term_path in term_paths if path[: len(term_path)] == term_path]
    if not matching:
        return ()
    return max(matching, key=len)


def find_or_rule_path(expr: Expr, kind: str) -> tuple[int, ...] | None:
    if expr["op"] != "or":
        return None
    terms = [(path, get_subexpr(expr, path)) for path in disjunct_paths(expr)]
    if kind == "false":
        for i, (path, term) in enumerate(terms):
            if term["op"] == "false":
                neighbor_index = i - 1 if i > 0 else i + 1
                if 0 <= neighbor_index < len(terms):
                    return common_prefix_path(path, terms[neighbor_index][0])
    if kind == "true":
        for i, (path, term) in enumerate(terms):
            if term["op"] == "true":
                neighbor_index = i - 1 if i > 0 else i + 1
                if 0 <= neighbor_index < len(terms):
                    return common_prefix_path(path, terms[neighbor_index][0])
    if kind == "duplicate":
        for i, (left_path, left_term) in enumerate(terms):
            for right_path, right_term in terms[i + 1 :]:
                if left_term == right_term:
                    return common_prefix_path(left_path, right_path)
    if kind == "absorption":
        term_keys = [term_key_set(term) for _, term in terms]
        for i, (left_path, _) in enumerate(terms):
            for j, (right_path, _) in enumerate(terms):
                if i != j and term_keys[i] < term_keys[j]:
                    return common_prefix_path(left_path, right_path)
    if kind == "adjacency":
        key_sets = [term_key_set(term) for _, term in terms]
        raw_terms = [flatten_and(term) for _, term in terms]
        for i, (left_path, _) in enumerate(terms):
            for j, (right_path, _) in enumerate(terms[i + 1 :], start=i + 1):
                diff_left = key_sets[i] - key_sets[j]
                diff_right = key_sets[j] - key_sets[i]
                if len(diff_left) != 1 or len(diff_right) != 1:
                    continue
                left_item = next(item for item in raw_terms[i] if expr_sort_key(item) in diff_left)
                right_item = next(item for item in raw_terms[j] if expr_sort_key(item) in diff_right)
                if is_negation_pair(left_item, right_item):
                    return common_prefix_path(left_path, right_path)
    return None


def simplify_one_term(current: Expr, steps: list[Step], term_path: tuple[int, ...]) -> tuple[Expr, bool]:
    changed_any = False
    for _ in range(64):
        changed = False
        term = get_subexpr(current, term_path)
        local_path = find_term_rule_path(term, "complement")
        if local_path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                term_path + local_path,
                "COMPLEMENT",
                "Apply complement.",
                rule_complement,
                local_ops={"and"},
                max_steps=5,
            )
        if changed:
            changed_any = True
            continue

        local_path = find_term_rule_path(term, "false")
        if local_path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                term_path + local_path,
                "ANNIHILATION",
                "Apply annihilation.",
                rule_annihilation,
                local_ops={"and"},
                max_steps=4,
            )
        if changed:
            changed_any = True
            continue

        local_path = find_term_rule_path(term, "true")
        if local_path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                term_path + local_path,
                "IDENTITY",
                "Apply identity.",
                rule_identity,
                local_ops={"and"},
                max_steps=4,
            )
        if changed:
            changed_any = True
            continue

        local_path = find_term_rule_path(term, "duplicate")
        if local_path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                term_path + local_path,
                "IDEMPOTENCE",
                "Apply idempotence.",
                rule_idempotence,
                local_ops={"and"},
                max_steps=4,
            )
        if changed:
            changed_any = True
            continue

        break
    return current, changed_any


def prepare_subtree_for_rule(
    expr: Expr,
    target_rule_fn: Any,
    *,
    local_ops: set[str] | None,
    max_steps: int = 6,
) -> tuple[Expr, list[dict[str, Any]], bool]:
    _, available = rewrite_once(expr, target_rule_fn)
    if available:
        return deepcopy(expr), [], True

    queue: deque[tuple[Expr, list[dict[str, Any]]]] = deque([(deepcopy(expr), [])])
    seen = {structural_fingerprint(expr)}

    while queue:
        candidate, path_steps = queue.popleft()
        if len(path_steps) >= max_steps:
            continue
        for rule_name, description, variant in enumerate_structural_rewrites(candidate, local_ops):
            fingerprint = structural_fingerprint(variant)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            next_steps = [
                *path_steps,
                {"rule": rule_name, "description": description, "expr": deepcopy(variant)},
            ]
            _, available = rewrite_once(variant, target_rule_fn)
            if available:
                return variant, next_steps, True
            queue.append((variant, next_steps))
    return deepcopy(expr), [], False


def apply_local_steps(
    current: Expr, whole_steps: list[Step], path: tuple[int, ...], local_steps: list[dict[str, Any]]
) -> Expr:
    updated = deepcopy(current)
    for local_step in local_steps:
        updated = replace_subexpr(updated, path, local_step["expr"])
        add_step(whole_steps, local_step["rule"], local_step["description"], updated)
    return updated


def apply_rule_at_path(
    current: Expr,
    whole_steps: list[Step],
    path: tuple[int, ...],
    rule_name: str,
    description: str,
    rule_fn: Any,
    *,
    local_ops: set[str] | None,
    max_steps: int = 6,
) -> tuple[Expr, bool]:
    subtree = get_subexpr(current, path)
    prepared, prep_steps, exposed = prepare_subtree_for_rule(
        subtree,
        rule_fn,
        local_ops=local_ops,
        max_steps=max_steps,
    )
    if not exposed:
        return current, False
    current = apply_local_steps(current, whole_steps, path, prep_steps)
    rewritten, changed = rewrite_once(prepared, rule_fn)
    if not changed:
        raise RuntimeError(f"Failed to expose {rule_name} at selected subtree")
    current = replace_subexpr(current, path, rewritten)
    add_step(whole_steps, rule_name, description, current)
    return current, True


def rule_idempotence(expr: Expr) -> Expr | None:
    if expr["op"] not in {"and", "or"}:
        return None
    left, right = expr["args"]
    if left == right:
        return deepcopy(left)
    return None


def rule_complement(expr: Expr) -> Expr | None:
    if expr["op"] not in {"and", "or"}:
        return None
    left, right = expr["args"]
    if not is_negation_pair(left, right):
        return None
    return {"op": "false" if expr["op"] == "and" else "true", "args": []}


def rule_identity(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if left["op"] == "true":
            return deepcopy(right)
        if right["op"] == "true":
            return deepcopy(left)
    if expr["op"] == "or":
        left, right = expr["args"]
        if left["op"] == "false":
            return deepcopy(right)
        if right["op"] == "false":
            return deepcopy(left)
    return None


def rule_annihilation(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if right["op"] == "false":
            return {"op": "false", "args": []}
    if expr["op"] == "or":
        left, right = expr["args"]
        if right["op"] == "true":
            return {"op": "true", "args": []}
    return None


def rule_absorption(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if right["op"] == "or" and (left == right["args"][0] or left == right["args"][1]):
            return deepcopy(left)
        if left["op"] == "or" and (right == left["args"][0] or right == left["args"][1]):
            return deepcopy(right)
    if expr["op"] == "or":
        left, right = expr["args"]
        if right["op"] == "and" and (left == right["args"][0] or left == right["args"][1]):
            return deepcopy(left)
        if left["op"] == "and" and (right == left["args"][0] or right == left["args"][1]):
            return deepcopy(right)
    return None


def rule_reduction(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if right["op"] == "or":
            if is_negation_pair(left, right["args"][0]):
                return mk("and", deepcopy(left), deepcopy(right["args"][1]))
            if is_negation_pair(left, right["args"][1]):
                return mk("and", deepcopy(left), deepcopy(right["args"][0]))
        if left["op"] == "or":
            if is_negation_pair(right, left["args"][0]):
                return mk("and", deepcopy(right), deepcopy(left["args"][1]))
            if is_negation_pair(right, left["args"][1]):
                return mk("and", deepcopy(right), deepcopy(left["args"][0]))
    if expr["op"] == "or":
        left, right = expr["args"]
        if right["op"] == "and":
            if is_negation_pair(left, right["args"][0]):
                return mk("or", deepcopy(left), deepcopy(right["args"][1]))
            if is_negation_pair(left, right["args"][1]):
                return mk("or", deepcopy(left), deepcopy(right["args"][0]))
        if left["op"] == "and":
            if is_negation_pair(right, left["args"][0]):
                return mk("or", deepcopy(right), deepcopy(left["args"][1]))
            if is_negation_pair(right, left["args"][1]):
                return mk("or", deepcopy(right), deepcopy(left["args"][0]))
    return None


def rule_adjacency(expr: Expr) -> Expr | None:
    if expr["op"] == "and":
        left, right = expr["args"]
        if left["op"] == "or" and right["op"] == "or":
            for i in range(2):
                for j in range(2):
                    if left["args"][i] == right["args"][j] and is_negation_pair(
                        left["args"][1 - i], right["args"][1 - j]
                    ):
                        return deepcopy(left["args"][i])
    if expr["op"] == "or":
        left, right = expr["args"]
        if left["op"] == "and" and right["op"] == "and":
            for i in range(2):
                for j in range(2):
                    if left["args"][i] == right["args"][j] and is_negation_pair(
                        left["args"][1 - i], right["args"][1 - j]
                    ):
                        return deepcopy(left["args"][i])
    return None


def canonicalize_conjunction(expr: Expr) -> Expr:
    items = flatten_and(expr)
    literal_counts: dict[str, int] = {}
    for item in items:
        if item["op"] == "knight":
            literal_counts[item["person"]] = literal_counts.get(item["person"], 0) + 1
        elif item["op"] == "not" and item["args"][0]["op"] == "knight":
            person = item["args"][0]["person"]
            literal_counts[person] = literal_counts.get(person, 0) + 1

    def conj_key(item: Expr) -> tuple[Any, ...]:
        if item["op"] == "true":
            return (2, 0, "", 0)
        if item["op"] == "knight":
            return (1, -literal_counts.get(item["person"], 1), item["person"], 0)
        if item["op"] == "not" and item["args"][0]["op"] == "knight":
            person = item["args"][0]["person"]
            return (1, -literal_counts.get(person, 1), person, 1)
        if item["op"] == "false":
            return (4, 0, "", 0)
        return (3, *expr_sort_key(item))

    items = sorted(items, key=conj_key)
    return make_and(items)


def canonicalize_disjunction(expr: Expr) -> Expr:
    terms = sorted(flatten_or(expr), key=term_signature)
    canonical_terms = [canonicalize_conjunction(term) for term in terms]
    return make_or(canonical_terms)


def canonicalize_dnf(expr: Expr) -> Expr:
    if expr["op"] == "or":
        return canonicalize_disjunction(expr)
    return canonicalize_conjunction(expr)


def normalize_to_nnf(expr: Expr) -> tuple[Expr, list[Step]]:
    current = deepcopy(expr)
    steps: list[Step] = []

    current, new_steps = apply_rule_until_fixed(
        current,
        "DOUBLENEGATION_EQUIV",
        "Eliminate double negations.",
        rule_double_negation,
    )
    steps.extend(new_steps)

    changed = True
    while changed:
        changed = False

        current, new_steps = apply_rule_until_fixed(
            current,
            "DE_MORGAN",
            "Push negations inward using De Morgan's law.",
            rule_demorgan,
        )
        if new_steps:
            changed = True
            steps.extend(new_steps)

        current, new_steps = apply_rule_until_fixed(
            current,
            "DOUBLENEGATION_EQUIV",
            "Eliminate double negations.",
            rule_double_negation,
        )
        if new_steps:
            changed = True
            steps.extend(new_steps)

    return current, steps


def to_dnf(expr: Expr) -> tuple[Expr, list[Step]]:
    current = deepcopy(expr)
    steps: list[Step] = []

    for _ in range(4096):
        if is_dnf(current):
            break
        changed = False
        for path in distribution_candidate_paths(current):
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "DISTRIBUTION",
                "Distribute conjunction over disjunction to build DNF.",
                rule_distribution_dnf,
                local_ops={"and"},
                max_steps=5,
            )
            if changed:
                break
        if not changed:
            raise RuntimeError("Failed to expose a valid DISTRIBUTION redex while building DNF")

    return current, steps


def term_absorbs(left: Expr, right: Expr) -> bool:
    left_keys = {expr_sort_key(item) for item in flatten_and(left)}
    right_keys = {expr_sort_key(item) for item in flatten_and(right)}
    return left_keys < right_keys or left_keys == right_keys


def simplify_dnf(expr: Expr) -> tuple[Expr, list[Step]]:
    current = deepcopy(expr)
    steps: list[Step] = []

    for _ in range(4096):
        current, changed = rewrite_once(current, rule_double_negation)
        if changed:
            add_step(steps, "DOUBLENEGATION_EQUIV", "Eliminate double negations.", current)
            continue

        current, changed = rewrite_once(current, rule_inverse)
        if changed:
            add_step(steps, "INVERSE", "Replace negated constants with their complements.", current)
            continue

        changed = False

        path = find_term_rule_path(current, "complement")
        if path is not None:
            current, changed = simplify_one_term(current, steps, containing_term_path(current, path))
        if changed:
            continue

        path = find_term_rule_path(current, "false")
        if path is not None:
            current, changed = simplify_one_term(current, steps, containing_term_path(current, path))
        if changed:
            continue

        path = find_or_rule_path(current, "true")
        if path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "ANNIHILATION",
                "Apply annihilation.",
                rule_annihilation,
                local_ops={"or"},
                max_steps=6,
            )
        if changed:
            continue

        path = find_or_rule_path(current, "false")
        if path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "IDENTITY",
                "Apply identity.",
                rule_identity,
                local_ops={"or"},
                max_steps=6,
            )
        if changed:
            continue

        path = find_or_rule_path(current, "duplicate")
        if path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "IDEMPOTENCE",
                "Apply idempotence.",
                rule_idempotence,
                local_ops={"or"},
                max_steps=6,
            )
        if changed:
            continue

        path = find_term_rule_path(current, "true")
        if path is not None:
            current, changed = simplify_one_term(current, steps, containing_term_path(current, path))
        if changed:
            continue

        path = find_term_rule_path(current, "duplicate")
        if path is not None:
            current, changed = simplify_one_term(current, steps, containing_term_path(current, path))
        if changed:
            continue

        path = find_or_rule_path(current, "adjacency")
        if path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "ADJACENCY",
                "Apply adjacency.",
                rule_adjacency,
                local_ops={"or"},
                max_steps=6,
            )
        if changed:
            continue

        path = find_or_rule_path(current, "absorption")
        if path is not None:
            current, changed = apply_rule_at_path(
                current,
                steps,
                path,
                "ABSORPTION",
                "Apply absorption.",
                rule_absorption,
                local_ops={"or"},
                max_steps=6,
            )
        if changed:
            continue

        if current["op"] == "and":
            current, changed = apply_rule_at_path(
                current,
                steps,
                (),
                "REDUCTION",
                "Apply reduction.",
                rule_reduction,
                local_ops={"and"},
                max_steps=5,
            )
            if changed:
                changed = True
                continue

        break

    return current, steps


def assignment_bit_masks(people: list[str]) -> tuple[int, dict[str, int]]:
    rows = 1 << len(people)
    masks: dict[str, int] = {}
    for index, person in enumerate(people):
        shift = len(people) - 1 - index
        mask = 0
        for row in range(rows):
            if (row >> shift) & 1:
                mask |= 1 << row
        masks[person] = mask
    return rows, masks


def freeze_expr(expr: Expr) -> tuple[Any, ...]:
    op = expr["op"]
    if op == "knight":
        return ("knight", expr["person"])
    if op in {"true", "false"}:
        return (op,)
    return (op, *(freeze_expr(arg) for arg in expr["args"]))


def solve_puzzle(people: list[str], constraints: list[Expr]) -> list[dict[str, bool]]:
    rows, masks = assignment_bit_masks(people)
    full_mask = (1 << rows) - 1

    @lru_cache(maxsize=None)
    def eval_expr_mask(frozen: tuple[Any, ...]) -> int:
        op = frozen[0]
        if op == "knight":
            return masks[frozen[1]]
        if op == "true":
            return full_mask
        if op == "false":
            return 0
        if op == "not":
            return full_mask ^ eval_expr_mask(frozen[1])
        if op == "and":
            return eval_expr_mask(frozen[1]) & eval_expr_mask(frozen[2])
        if op == "or":
            return eval_expr_mask(frozen[1]) | eval_expr_mask(frozen[2])
        if op == "eq":
            left = eval_expr_mask(frozen[1])
            right = eval_expr_mask(frozen[2])
            return full_mask ^ (left ^ right)
        raise ValueError(f"Unknown op: {op}")

    satisfying = full_mask
    for constraint in constraints:
        satisfying &= eval_expr_mask(freeze_expr(constraint))

    all_solutions: list[dict[str, bool]] = []
    for row in range(rows):
        if not ((satisfying >> row) & 1):
            continue
        assignment = {
            person: bool((row >> (len(people) - 1 - index)) & 1)
            for index, person in enumerate(people)
        }
        all_solutions.append(assignment)
    return all_solutions


def as_knights_knaves(solution: dict[str, bool]) -> dict[str, str]:
    return {person: ("knight" if is_knight else "knave") for person, is_knight in solution.items()}


def as_literal_conjunction(solution: dict[str, bool], people_order: list[str]) -> str:
    parts: list[str] = []
    for person in people_order:
        parts.append(person.lower() if solution[person] else f"not {person.lower()}")
    return " and ".join(parts)


def as_answer_text(solution: dict[str, bool], people_order: list[str]) -> str:
    parts = [
        f"{person} is a {'knight' if solution[person] else 'knave'}"
        for person in people_order
    ]
    return ", ".join(parts)


def format_final_answer(people: list[str], assignments: list[dict[str, bool]]) -> str:
    if not assignments:
        return "So the answer is: no consistent assignment."
    if len(assignments) == 1:
        return f"So the answer is: {as_answer_text(assignments[0], people)}."
    rendered = "; ".join(as_answer_text(solution, people) for solution in assignments)
    return f"So the possible answers are: {rendered}."


def assignment_key(people: list[str], assignment: dict[str, bool]) -> tuple[bool, ...]:
    return tuple(assignment[person] for person in people)


def merge_implicants(
    left: tuple[bool | None, ...], right: tuple[bool | None, ...]
) -> tuple[bool | None, ...] | None:
    diff_index = -1
    for index, (left_bit, right_bit) in enumerate(zip(left, right)):
        if left_bit == right_bit:
            continue
        if left_bit is None or right_bit is None:
            return None
        if diff_index != -1:
            return None
        diff_index = index
    if diff_index == -1:
        return None
    merged = list(left)
    merged[diff_index] = None
    return tuple(merged)


def implicant_covers(
    implicant: tuple[bool | None, ...], assignment: tuple[bool, ...]
) -> bool:
    return all(bit is None or bit == value for bit, value in zip(implicant, assignment))


def implicant_sort_key(implicant: tuple[bool | None, ...]) -> tuple[Any, ...]:
    rank = {True: 0, False: 1, None: 2}
    return tuple(rank[bit] for bit in implicant)


def minimize_assignments(people: list[str], assignments: list[dict[str, bool]]) -> list[tuple[bool | None, ...]]:
    if not assignments:
        return []

    current = {assignment_key(people, assignment) for assignment in assignments}
    prime_implicants: set[tuple[bool | None, ...]] = set()

    while current:
        used: set[tuple[bool | None, ...]] = set()
        next_round: set[tuple[bool | None, ...]] = set()
        ordered = sorted(current, key=implicant_sort_key)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                merged = merge_implicants(left, right)
                if merged is None:
                    continue
                used.add(left)
                used.add(right)
                next_round.add(merged)
        prime_implicants.update(item for item in current if item not in used)
        current = next_round

    targets = {assignment_key(people, assignment) for assignment in assignments}
    coverage = {
        implicant: {target for target in targets if implicant_covers(implicant, target)}
        for implicant in prime_implicants
    }

    selected: list[tuple[bool | None, ...]] = []
    uncovered = set(targets)

    for target in sorted(targets):
        covering = [implicant for implicant, covered in coverage.items() if target in covered]
        if len(covering) == 1 and covering[0] not in selected:
            selected.append(covering[0])
            uncovered -= coverage[covering[0]]

    while uncovered:
        best = max(
            (implicant for implicant in coverage if implicant not in selected),
            key=lambda implicant: (len(coverage[implicant] & uncovered), tuple(-x for x in implicant_sort_key(implicant))),
        )
        selected.append(best)
        uncovered -= coverage[best]

    return sorted(selected, key=implicant_sort_key)


def formula_from_assignments(
    people: list[str], assignments: list[dict[str, bool]]
) -> Expr:
    if not assignments:
        return {"op": "false", "args": []}
    use_minimized_implicants = len(assignments) <= 32 and len(people) <= 6
    terms = []
    implicants: list[tuple[bool | None, ...]]
    if use_minimized_implicants:
        implicants = minimize_assignments(people, assignments)
    else:
        implicants = [assignment_key(people, assignment) for assignment in assignments]
    for implicant in implicants:
        term_items = []
        for person, value in zip(people, implicant):
            if value is None:
                continue
            term_items.append(atom(person) if value else mk("not", atom(person)))
        if not term_items:
            return {"op": "true", "args": []}
        terms.append(make_and(term_items))
    return canonicalize_dnf(make_or(terms))


def simplify_canonical_dnf(expr: Expr, max_rounds: int = 8) -> Expr:
    current = canonicalize_dnf(expr)
    for _ in range(max_rounds):
        updated, _ = simplify_dnf(current)
        updated = canonicalize_dnf(updated)
        if updated == current:
            break
        current = updated
    return current


def print_puzzle_steps(puzzle: dict[str, Any]) -> None:
    print(f"Puzzle {puzzle['id']}")
    print(f"People: {', '.join(puzzle['people'])}")
    for idx, step in enumerate(puzzle["equivalence_steps"], start=1):
        print(f"  Step {idx}: {step['rule']}")
        print(f"    {step['description']}")
        print(f"    {step['formula']}")
    print(f"  Final formula: {puzzle['final_formula']}")
    print(f"  Solution count: {puzzle['solution_count']}")
    for idx, rendered in enumerate(puzzle.get("solution_literals", []), start=1):
        print(f"    Solution {idx}: {rendered}")
    print(f"  {puzzle['answer']}")
    print()


def compress_step_run(run: list[Step], keep: int = 4) -> list[Step]:
    if len(run) <= keep:
        return run
    head = keep // 2
    tail = keep - head
    return [*run[:head], *run[-tail:]]


def compact_equivalence_steps(
    steps: list[Step], max_run_per_rule: int = 4, max_total_steps: int = 80
) -> list[Step]:
    if len(steps) <= 2:
        return steps

    compacted: list[Step] = [steps[0]]
    current_run: list[Step] = [steps[1]]

    for step in steps[2:]:
        if step["rule"] == current_run[-1]["rule"]:
            current_run.append(step)
            continue
        compacted.extend(compress_step_run(current_run, keep=max_run_per_rule))
        current_run = [step]

    compacted.extend(compress_step_run(current_run, keep=max_run_per_rule))
    if len(compacted) > max_total_steps:
        head = max_total_steps // 2
        tail = max_total_steps - head
        compacted = [*compacted[:head], *compacted[-tail:]]
    return compacted


def build_steps(constraints: list[Expr], *, compact: bool = True) -> tuple[Expr, list[Step]]:
    combined = make_and([deepcopy(constraint) for constraint in constraints])
    steps: list[Step] = [
        {
            "rule": "START",
            "description": "Conjoin all speaker truth constraints.",
            "formula": expr_to_str(combined),
        }
    ]

    current = deepcopy(combined)
    current, new_steps = apply_rule_until_fixed(
        current,
        "BICONDITIONAL_EQUIVALENCE",
        "Replace biconditionals with equivalent disjunctive cases.",
        rule_biconditional_equivalence,
    )
    steps.extend(new_steps)

    current, new_steps = normalize_to_nnf(current)
    steps.extend(new_steps)

    current, new_steps = to_dnf(current)
    steps.extend(new_steps)

    current, new_steps = simplify_dnf(current)
    steps.extend(new_steps)

    if compact:
        return current, compact_equivalence_steps(steps)
    return current, steps


def verify_step_equivalence(steps: list[Step]) -> bool:
    if len(steps) < 2:
        return True
    formulas = [parse_formula_text(step["formula"]) for step in steps]
    people = sorted(set().union(*(gather_people(expr) for expr in formulas)))
    for left, right in zip(formulas, formulas[1:]):
        for bits in itertools.product([False, True], repeat=len(people)):
            assignment = dict(zip(people, bits))
            if eval_expr(left, assignment) != eval_expr(right, assignment):
                return False
    return True


def tokenize_formula(text: str) -> list[str]:
    tokens: list[str] = []
    idx = 0
    while idx < len(text):
        char = text[idx]
        if char.isspace():
            idx += 1
            continue
        if char in {"(", ")", "¬", "∧", "∨", "↔"}:
            tokens.append(char)
            idx += 1
            continue
        if char in {"⊤", "⊥"}:
            tokens.append(char)
            idx += 1
            continue
        if text.startswith("K_", idx):
            end = idx + 2
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(text[idx:end])
            idx = end
            continue
        raise ValueError(f"Unexpected character in formula: {char!r}")
    return tokens


class FormulaParser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def consume(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("Unexpected end of formula")
        if expected is not None and token != expected:
            raise ValueError(f"Expected {expected!r}, got {token!r}")
        self.pos += 1
        return token

    def parse(self) -> Expr:
        expr = self.parse_binary()
        if self.peek() is not None:
            raise ValueError(f"Unexpected trailing token: {self.peek()!r}")
        return expr

    def parse_binary(self) -> Expr:
        token = self.peek()
        if token == "(":
            self.consume("(")
            left = self.parse_binary()
            if self.peek() == ")":
                self.consume(")")
                return left
            operator = self.consume()
            right = self.parse_binary()
            self.consume(")")
            if operator == "∧":
                return mk("and", left, right)
            if operator == "∨":
                return mk("or", left, right)
            if operator == "↔":
                return mk("eq", left, right)
            raise ValueError(f"Unexpected operator: {operator!r}")
        return self.parse_unary()

    def parse_unary(self) -> Expr:
        token = self.peek()
        if token == "¬":
            self.consume("¬")
            if self.peek() == "(":
                return mk("not", self.parse_binary())
            return mk("not", self.parse_unary())
        if token == "⊤":
            self.consume("⊤")
            return {"op": "true", "args": []}
        if token == "⊥":
            self.consume("⊥")
            return {"op": "false", "args": []}
        if token is None:
            raise ValueError("Unexpected end of formula")
        if token.startswith("K_"):
            self.consume()
            return atom(token[2:])
        raise ValueError(f"Unexpected token: {token!r}")


def parse_formula_text(text: str) -> Expr:
    return FormulaParser(tokenize_formula(text)).parse()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/knights_and_knaves_logic.json"),
        help="Converted puzzle logic JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/knights_and_knaves_solutions.json"),
        help="Output path for solved puzzles with equivalence steps",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional puzzle limit for quick runs",
    )
    parser.add_argument(
        "--puzzle-id",
        type=int,
        action="append",
        default=None,
        help="Solve only this puzzle id. Repeat to include multiple ids.",
    )
    parser.add_argument(
        "-p",
        "--problem",
        dest="problem",
        type=int,
        default=None,
        help="Solve only one puzzle id.",
    )
    parser.add_argument(
        "--print-steps",
        action="store_true",
        help="Print equivalence steps and solutions to stdout.",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    puzzles = data["puzzles"]
    selected_ids = set(args.puzzle_id or [])
    if args.problem is not None:
        selected_ids.add(args.problem)

    if selected_ids:
        puzzles = [puzzle for puzzle in puzzles if puzzle["id"] in selected_ids]
    if args.limit is not None:
        puzzles = puzzles[: args.limit]

    solved_puzzles: list[dict[str, Any]] = []
    unique_count = 0

    for puzzle in puzzles:
        people = puzzle["people"]
        constraints = puzzle["constraints"]
        assignments = solve_puzzle(people, constraints)
        final_formula, steps = build_steps(constraints)
        _, aris_steps = build_steps(constraints, compact=False)

        if len(assignments) == 1:
            unique_count += 1

        solved_puzzles.append(
            {
                "id": puzzle["id"],
                "people": people,
                "equivalence_steps": steps,
                "aris_steps": aris_steps,
                "final_formula": expr_to_str(final_formula),
                "solution_count": len(assignments),
                "solution_literals": [as_literal_conjunction(solution, people) for solution in assignments],
                "solutions": [as_knights_knaves(solution) for solution in assignments],
                "answer": format_final_answer(people, assignments),
            }
        )

    output = {
        "source_logic": str(args.input),
        "puzzle_count": len(solved_puzzles),
        "unique_solution_count": unique_count,
        "operators_used": ["not", "and", "or", "eq"],
        "rule_set": [
            "BICONDITIONAL_EQUIVALENCE",
            "DOUBLENEGATION_EQUIV",
            "DE_MORGAN",
            "DISTRIBUTION",
            "COMMUTATION",
            "ASSOCIATION",
            "COMPLEMENT",
            "IDENTITY",
            "ANNIHILATION",
            "INVERSE",
            "IDEMPOTENCE",
            "ABSORPTION",
            "REDUCTION",
            "ADJACENCY",
        ],
        "puzzles": solved_puzzles,
    }

    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {args.output}")
    print(
        f"Solved {len(solved_puzzles)} puzzles; "
        f"{unique_count} with a unique solution"
    )
    if args.print_steps:
        print()
        for puzzle in solved_puzzles:
            print_puzzle_steps(puzzle)


if __name__ == "__main__":
    main()
