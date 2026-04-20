# Knights and Knaves Solver

Converts Knights and Knaves puzzles into boolean logic, solves them step-by-step using
equivalence rules, and exports proofs as `.bram` files importable into
[aris.bram-hub.com](https://aris.bram-hub.com).

Puzzle source: <http://philosophy.hku.hk/think/logic/knights.php> — licensed CC BY-SA 4.0
(see [LICENSE-DATA.md](LICENSE-DATA.md)).

---

## Pipeline

### Step 1 — Parse puzzles to logic JSON

```bash
python3 scripts/convert_knights_knaves.py \
  --input "data/Knights and Knaves.md" \
  --output data/knights_and_knaves_logic.json
```

Reads the markdown puzzle file and emits a JSON file where each puzzle has:
- `people`: list of inhabitants
- `utterances`: each speaker's statement as a boolean formula
- `constraints`: `knight(speaker) ↔ statement` for each utterance

### Step 2 — Solve puzzles and generate proofs

```bash
python3 scripts/solve_knights_knaves.py \
  --input data/knights_and_knaves_logic.json \
  --output data/knights_and_knaves_solutions.json
```

For each puzzle, reduces the conjunction of constraints to DNF using boolean algebra
equivalence rules, recording every transformation step. Each step in the output has:
- `rule`: the equivalence rule applied
- `formula`: the formula after applying the rule
- `description`: plain-English explanation

### Step 3 — Export a proof to `.bram`

```bash
python3 scripts/export_bram_proof.py <puzzle_number>
```

Writes `data/bram/puzzle_<N>.bram`. Options:
- `--input PATH` — solutions JSON (default: `data/knights_and_knaves_solutions.json`)
- `--output PATH` — output `.bram` file
- `--author NAME` — author field in metadata (default: `mikehalpern`)

**Example:**
```bash
python3 scripts/export_bram_proof.py 1
# Wrote data/bram/puzzle_1.bram
# Symbol map: Zoey->A, Mel->B
# Goal: (A ∧ ¬B)
```

### Importing into Aris

1. Open [aris.bram-hub.com](https://aris.bram-hub.com)
2. Use **File → Open** and select a `.bram` file from `data/bram/`
3. The proof loads with all equivalence steps and the goal highlighted

---

## Formula Notation

| Symbol | Meaning |
|--------|---------|
| `A`, `B`, `C`, … | Person variables (A = first person listed, B = second, …) |
| `¬` | NOT (negation) |
| `∧` | AND (conjunction) |
| `∨` | OR (disjunction) |
| `↔` | Biconditional (if and only if) |
| `⊤` | True (tautology) |
| `⊥` | False (contradiction) |

---

## Equivalence Rules

The solver uses 14 boolean algebra equivalence rules:

| Rule | Law |
|------|-----|
| `BICONDITIONAL_EQUIVALENCE` | A ↔ B = (A ∧ B) ∨ (¬A ∧ ¬B) |
| `DOUBLENEGATION_EQUIV` | ¬¬A = A |
| `DE_MORGAN` | ¬(A ∧ B) = ¬A ∨ ¬B; ¬(A ∨ B) = ¬A ∧ ¬B |
| `DISTRIBUTION` | A ∧ (B ∨ C) = (A ∧ B) ∨ (A ∧ C) |
| `COMMUTATION` | A ∧ B = B ∧ A; A ∨ B = B ∨ A |
| `ASSOCIATION` | (A ∧ B) ∧ C = A ∧ (B ∧ C) |
| `COMPLEMENT` | A ∧ ¬A = ⊥; A ∨ ¬A = ⊤ |
| `IDENTITY` | A ∧ ⊤ = A; A ∨ ⊥ = A |
| `ANNIHILATION` | A ∧ ⊥ = ⊥; A ∨ ⊤ = ⊤ |
| `INVERSE` | ¬⊤ = ⊥; ¬⊥ = ⊤ |
| `IDEMPOTENCE` | A ∧ A = A; A ∨ A = A |
| `ABSORPTION` | A ∨ (A ∧ B) = A |
| `REDUCTION` | A ∧ (¬A ∨ B) = A ∧ B |
| `ADJACENCY` | (A ∧ B) ∨ (A ∧ ¬B) = A |

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Helper Scripts

```bash
# Display parsed logic formulas for a puzzle
python3 scripts/render_logic_formulas.py --puzzle-id 1

# View a solved puzzle's result and proof steps
python3 scripts/view_puzzle_solution.py 1 --steps
```
