import json
import time
import unittest
from pathlib import Path

from scripts.convert_knights_knaves import parse_expr
from scripts.solve_knights_knaves import (
    as_answer_text,
    atom,
    assert_valid_proof_steps,
    build_steps,
    canonicalize_dnf,
    format_final_answer,
    enumerate_structural_rewrites,
    eval_expr,
    expr_to_str,
    is_dnf,
    make_and,
    make_or,
    mk,
    parse_formula_text,
    prepare_subtree_for_rule,
    rewrite_once,
    rule_annihilation,
    rule_association,
    rule_commutation,
    rule_complement,
    simplify_dnf,
    validate_proof_steps,
    verify_step_equivalence,
)


DATA_PATH = Path("data/knights_and_knaves_logic.json")


class SolveKnightsKnavesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.logic = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.puzzles = {puzzle["id"]: puzzle for puzzle in cls.logic["puzzles"]}

    def test_formula_parser_round_trip(self) -> None:
        expr = mk("or", make_and([atom("A"), mk("not", atom("B"))]), {"op": "false", "args": []})
        parsed = parse_formula_text("((K_A ∧ ¬K_B) ∨ ⊥)")
        self.assertEqual(parsed, expr)

    def test_is_dnf_and_canonicalize(self) -> None:
        expr = make_or(
            [
                make_and([mk("not", atom("B")), atom("A")]),
                make_and([atom("A"), mk("not", atom("B"))]),
            ]
        )
        self.assertTrue(is_dnf(expr))
        canonical = canonicalize_dnf(expr)
        self.assertTrue(is_dnf(canonical))
        self.assertEqual(
            canonical,
            make_or(
                [
                    make_and([atom("A"), mk("not", atom("B"))]),
                    make_and([atom("A"), mk("not", atom("B"))]),
                ]
            ),
        )

    def test_simplify_dnf_absorbs_more_specific_term(self) -> None:
        expr = make_or([atom("A"), make_and([atom("A"), atom("B")])])
        simplified, _ = simplify_dnf(expr)
        self.assertEqual(simplified, atom("A"))

    def test_simplify_dnf_uses_repeated_annihilation_for_contradictory_term(self) -> None:
        expr = make_and([atom("A"), mk("not", atom("A")), atom("B")])
        simplified, steps = simplify_dnf(expr)
        self.assertEqual(simplified, {"op": "false", "args": []})
        self.assertEqual(sum(step["rule"] == "COMPLEMENT" for step in steps), 1)
        self.assertGreaterEqual(sum(step["rule"] == "ANNIHILATION" for step in steps), 1)

    def test_only_a_knave_would_say_statement_parses_as_negated_inner_claim(self) -> None:
        parsed = parse_expr(
            "Only a knave would say that Peggy is a knave",
            "Zippy",
            {"Peggy", "Zippy"},
        )
        self.assertEqual(parsed, atom("Peggy"))

    def test_build_steps_puzzle_one_reaches_expected_answer(self) -> None:
        puzzle = self.puzzles[1]
        final_formula, steps = build_steps(puzzle["constraints"])
        self.assertEqual(
            canonicalize_dnf(final_formula),
            canonicalize_dnf(make_and([atom("Zoey"), mk("not", atom("Mel"))])),
        )
        self.assertTrue(verify_step_equivalence(steps))
        self.assertLessEqual(sum(step["rule"] == "ASSOCIATION" for step in steps), 30)

    def test_puzzle_one_does_not_oscillate_between_association_forms(self) -> None:
        puzzle = self.puzzles[1]
        _, steps = build_steps(puzzle["constraints"])
        formulas = [step["formula"] for step in steps]
        for i in range(len(formulas) - 3):
            self.assertFalse(
                formulas[i] == formulas[i + 2] and formulas[i + 1] == formulas[i + 3],
                "proof oscillates between equivalent forms",
            )

    def test_structural_and_annihilation_steps_are_local(self) -> None:
        puzzle = self.puzzles[1]
        _, steps = build_steps(puzzle["constraints"])
        formulas = [parse_formula_text(step["formula"]) for step in steps]
        for index in range(1, len(steps)):
            rule = steps[index]["rule"]
            if rule not in {"COMMUTATION", "ASSOCIATION", "ANNIHILATION"}:
                continue
            previous = formulas[index - 1]
            current = formulas[index]
            if rule == "COMMUTATION":
                structural_variants = [
                    expr for name, _, expr in enumerate_structural_rewrites(previous) if name == "COMMUTATION"
                ]
                self.assertIn(current, structural_variants, "COMMUTATION step should be a single local rewrite")
                continue
            elif rule == "ASSOCIATION":
                structural_variants = [
                    expr for name, _, expr in enumerate_structural_rewrites(previous) if name == "ASSOCIATION"
                ]
                self.assertIn(current, structural_variants, "ASSOCIATION step should be a single local rewrite")
                continue
            else:
                expected, changed = rewrite_once(previous, rule_annihilation)
            self.assertTrue(changed, f"{rule} step should apply to previous formula")
            self.assertEqual(expected, current, f"{rule} step should be a single local rewrite")

    def test_rule_shape_validator_accepts_listed_aris_rules(self) -> None:
        a = atom("A")
        b = atom("B")
        c = atom("C")
        cases = [
            ("ASSOCIATION", mk("and", a, mk("and", b, c)), mk("and", mk("and", a, b), c)),
            ("COMMUTATION", mk("or", a, b), mk("or", b, a)),
            ("IDEMPOTENCE", mk("and", a, a), a),
            ("DE_MORGAN", mk("not", mk("or", a, b)), mk("and", mk("not", a), mk("not", b))),
            ("DISTRIBUTION", mk("and", a, mk("or", b, c)), mk("or", mk("and", a, b), mk("and", a, c))),
            ("DOUBLENEGATION_EQUIV", mk("not", mk("not", a)), a),
            ("COMPLEMENT", mk("and", a, mk("not", a)), {"op": "false", "args": []}),
            ("IDENTITY", mk("or", a, {"op": "false", "args": []}), a),
            ("ANNIHILATION", mk("and", a, {"op": "false", "args": []}), {"op": "false", "args": []}),
            ("INVERSE", mk("not", {"op": "true", "args": []}), {"op": "false", "args": []}),
            ("ABSORPTION", mk("or", a, mk("and", a, b)), a),
            ("REDUCTION", mk("and", a, mk("or", mk("not", a), b)), mk("and", a, b)),
            ("ADJACENCY", mk("or", mk("and", a, b), mk("and", a, mk("not", b))), a),
        ]
        for rule, previous, current in cases:
            steps = [
                {"rule": "START", "description": "", "formula": expr_to_str(previous)},
                {"rule": rule, "description": "", "formula": expr_to_str(current)},
            ]
            self.assertEqual(validate_proof_steps(steps), (True, None), rule)

    def test_rule_shape_validator_rejects_nonlocal_jump(self) -> None:
        steps = [
            {"rule": "START", "description": "", "formula": "(K_A ∧ (K_B ∧ K_C))"},
            {"rule": "ASSOCIATION", "description": "", "formula": "(K_C ∧ (K_B ∧ K_A))"},
        ]
        valid, error = validate_proof_steps(steps)
        self.assertFalse(valid)
        self.assertIn("line 1", error or "")

    def test_puzzle_two_has_expected_unique_solution(self) -> None:
        puzzle = self.puzzles[2]
        final_formula, steps = build_steps(puzzle["constraints"])
        expected = {"Peggy": False, "Zippy": False}
        for peggy in (False, True):
            for zippy in (False, True):
                assignment = {"Peggy": peggy, "Zippy": zippy}
                self.assertEqual(eval_expr(final_formula, assignment), assignment == expected)
        self.assertTrue(verify_step_equivalence(steps))

    def test_format_final_answer_is_concise_for_puzzle_two(self) -> None:
        answer = format_final_answer(
            ["Peggy", "Zippy"],
            [{"Peggy": False, "Zippy": False}],
        )
        self.assertEqual(answer, "So the answer is: Peggy is a knave, Zippy is a knave.")
        self.assertLess(len(answer), 80)

    def test_answer_text_renders_named_statuses(self) -> None:
        rendered = as_answer_text({"Peggy": False, "Zippy": False}, ["Peggy", "Zippy"])
        self.assertEqual(rendered, "Peggy is a knave, Zippy is a knave")

    def test_multi_solution_formula_stays_in_simplified_dnf(self) -> None:
        expr = make_or([atom("A"), atom("B")])
        final_formula, steps = build_steps([expr])
        self.assertEqual(final_formula, expr)
        self.assertTrue(is_dnf(final_formula))
        self.assertTrue(verify_step_equivalence(steps))

    def test_final_formula_matches_original_constraints_semantics(self) -> None:
        puzzle = self.puzzles[1]
        final_formula, _ = build_steps(puzzle["constraints"])
        for zoey in (False, True):
            for mel in (False, True):
                assignment = {"Zoey": zoey, "Mel": mel}
                original = all(eval_expr(constraint, assignment) for constraint in puzzle["constraints"])
                self.assertEqual(eval_expr(final_formula, assignment), original)

    def test_puzzles_two_and_four_complete_quickly(self) -> None:
        for puzzle_id in (2, 4):
            start = time.time()
            _, steps = build_steps(self.puzzles[puzzle_id]["constraints"])
            elapsed = time.time() - start
            self.assertLess(elapsed, 5.0)
            self.assertTrue(verify_step_equivalence(steps))
            assert_valid_proof_steps(steps)

    def test_sample_puzzle_proofs_are_aris_local(self) -> None:
        for puzzle_id in (1, 2, 3, 4, 7):
            _, steps = build_steps(self.puzzles[puzzle_id]["constraints"])
            assert_valid_proof_steps(steps)

    def test_puzzle_two_proof_is_uncompacted_and_valid(self) -> None:
        _, steps = build_steps(self.puzzles[2]["constraints"])
        self.assertGreater(len(steps), 80)
        assert_valid_proof_steps(steps)
        self.assertNotIn("TRUTH_TABLE_DNF", [step["rule"] for step in steps])

    def test_astar_local_search_falls_back_when_node_limit_is_low(self) -> None:
        expr = make_and([atom("A"), mk("not", atom("A")), atom("B")])
        _, normal_steps, normal_exposed = prepare_subtree_for_rule(
            expr,
            rule_complement,
            local_ops={"and"},
            max_steps=5,
        )
        _, fallback_steps, fallback_exposed = prepare_subtree_for_rule(
            expr,
            rule_complement,
            local_ops={"and"},
            max_steps=5,
            max_nodes=0,
        )
        self.assertTrue(normal_exposed)
        self.assertTrue(fallback_exposed)
        self.assertLessEqual(len(normal_steps), len(fallback_steps))


if __name__ == "__main__":
    unittest.main()
