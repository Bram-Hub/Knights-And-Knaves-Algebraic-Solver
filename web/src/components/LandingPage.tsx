import styles from './LandingPage.module.css';

export function LandingPage() {
  return (
    <div className={styles.page}>
      <div className={styles.content}>

        <header className={styles.hero}>
          <h1 className={styles.title}>Knights &amp; Knaves Solver</h1>
          <p className={styles.subtitle}>
            Automated boolean logic proofs for Raymond Smullyan's Knights and Knaves puzzles,
            exportable to <a href="https://aris.bram-hub.com" target="_blank" rel="noreferrer">Aris</a>.
          </p>
        </header>

        <section className={styles.section}>
          <h2>What are Knights and Knaves puzzles?</h2>
          <p>
            Knights and Knaves is a classic logic puzzle genre invented by logician Raymond Smullyan.
            Every inhabitant of the island is either a <strong>knight</strong> (who always tells the truth)
            or a <strong>knave</strong> (who always lies). Given a set of statements made by the inhabitants,
            your task is to determine who is a knight and who is a knave.
          </p>
          <div className={styles.example}>
            <div className={styles.exampleLabel}>Example — Puzzle #1</div>
            <div className={styles.utterance}>
              <span className={styles.speaker}>Zoey</span> says: <em>"Mel is a knave."</em>
            </div>
            <div className={styles.utterance}>
              <span className={styles.speaker}>Mel</span> says: <em>"Zoey and I are both knights."</em>
            </div>
            <div className={styles.exampleAnswer}>
              Answer: Zoey is a knight, Mel is a knave.
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>How it works</h2>
          <p>
            Each statement is encoded as a boolean constraint using the rule:
          </p>
          <code className={styles.formula}>K_Speaker ↔ statement</code>
          <p>
            (A speaker's claim is true if and only if they are a knight.)
            All constraints are conjoined and reduced to{' '}
            <strong>Disjunctive Normal Form (DNF)</strong> using 14 boolean algebra
            equivalence rules — the same rules used by the Aris proof assistant.
            Each rewrite step is recorded so the full derivation can be replayed and verified.
          </p>
        </section>

        <section className={styles.section}>
          <h2>Search algorithm</h2>
          <p>
            The solver does not guess or search by trial-and-error. Instead it uses
            purely algebraic rewriting — every step is a logically valid equivalence
            transformation, so the final form is guaranteed to equal the original
            constraint conjunction.
          </p>
          <p>The pipeline runs in four fixed phases:</p>
          <ol className={styles.algoSteps}>
            <li>
              <div className={styles.algoPhase}>Phase 1 — Encode</div>
              <div className={styles.algoDesc}>
                For each utterance by speaker <em>S</em> with statement <em>P</em>,
                emit the constraint <code>K_S ↔ P</code>. Conjoin all constraints
                into one big formula: <code>C₁ ∧ C₂ ∧ … ∧ Cₙ</code>.
              </div>
            </li>
            <li>
              <div className={styles.algoPhase}>Phase 2 — Eliminate biconditionals</div>
              <div className={styles.algoDesc}>
                Apply <strong>BICONDITIONAL_EQUIVALENCE</strong> repeatedly until
                every <code>↔</code> is replaced by an equivalent expression using
                only <code>∧</code>, <code>∨</code>, and <code>¬</code>.
                Rule: <code>A ↔ B = (A ∧ B) ∨ (¬A ∧ ¬B)</code>.
              </div>
            </li>
            <li>
              <div className={styles.algoPhase}>Phase 3 — Negation Normal Form (NNF)</div>
              <div className={styles.algoDesc}>
                Push all negations inward using <strong>DE_MORGAN</strong> and
                eliminate double negations with <strong>DOUBLENEGATION_EQUIV</strong>,
                so every <code>¬</code> appears only directly before a variable.
              </div>
            </li>
            <li>
              <div className={styles.algoPhase}>Phase 4 — Distribute to DNF</div>
              <div className={styles.algoDesc}>
                Apply <strong>DISTRIBUTION</strong> (<code>A ∧ (B ∨ C) = (A ∧ B) ∨ (A ∧ C)</code>)
                to push all <code>∧</code> inside <code>∨</code>, converting the formula
                into a disjunction of conjunctions (DNF). Then simplify using
                COMPLEMENT, IDENTITY, ANNIHILATION, IDEMPOTENCE, ABSORPTION,
                ADJACENCY, and REDUCTION to eliminate redundant clauses.
              </div>
            </li>
          </ol>
          <p>
            Each rule application is a single, targeted rewrite of one subformula —
            found by a depth-first left-first traversal. If the formula is not yet in
            the required position (e.g., the constant is on the wrong side), a
            preparatory <strong>COMMUTATION</strong> or <strong>ASSOCIATION</strong> step
            is automatically inserted. The result is a step-by-step proof that Aris can
            check mechanically, with every inference justified by exactly one rule.
          </p>
          <p>
            The final DNF form makes the solution immediately readable: each disjunct is
            a consistent assignment of people to knight or knave. If the DNF is <code>⊥</code>,
            the puzzle has no solution; if it has multiple disjuncts, there are multiple
            valid assignments.
          </p>
        </section>

        <section className={styles.section}>
          <h2>How to use this page</h2>
          <ol className={styles.steps}>
            <li>
              <span className={styles.stepNum}>1</span>
              <div>
                <strong>Browse or search</strong> the puzzle list on the left.
                Filter by puzzle number or a person's name. Puzzles marked{' '}
                <span className={styles.inlineBadge}>solved</span> have a cached
                proof ready immediately.
              </div>
            </li>
            <li>
              <span className={styles.stepNum}>2</span>
              <div>
                <strong>Select a puzzle</strong> to see who the inhabitants are
                and what each one claims.
              </div>
            </li>
            <li>
              <span className={styles.stepNum}>3</span>
              <div>
                Click <strong>Solve</strong> to run the boolean algebra solver.
                The proof steps will appear below, showing every equivalence rule
                applied from the initial constraints to the final DNF solution.
              </div>
            </li>
            <li>
              <span className={styles.stepNum}>4</span>
              <div>
                Click <strong>Download .bram</strong> to save the proof as a{' '}
                <code>.bram</code> file compatible with{' '}
                <a href="https://aris.bram-hub.com" target="_blank" rel="noreferrer">aris.bram-hub.com</a>.
                Open Aris, use <strong>File → Open</strong>, and select the file to
                load and verify the proof interactively.
              </div>
            </li>
          </ol>
        </section>

        <section className={styles.section}>
          <h2>Formula notation</h2>
          <table className={styles.table}>
            <thead>
              <tr><th>Symbol</th><th>Meaning</th></tr>
            </thead>
            <tbody>
              <tr><td><code>A</code>, <code>B</code>, <code>C</code>, …</td><td>Person variables (A = first person listed, B = second, …)</td></tr>
              <tr><td><code>¬</code></td><td>NOT (negation) — the person is a knave</td></tr>
              <tr><td><code>∧</code></td><td>AND (conjunction)</td></tr>
              <tr><td><code>∨</code></td><td>OR (disjunction)</td></tr>
              <tr><td><code>↔</code></td><td>Biconditional (if and only if)</td></tr>
              <tr><td><code>⊤</code></td><td>True (tautology)</td></tr>
              <tr><td><code>⊥</code></td><td>False (contradiction)</td></tr>
            </tbody>
          </table>
        </section>

        <section className={styles.section}>
          <h2>Equivalence rules</h2>
          <p>The solver applies these 14 boolean algebra rules, one at a time, at each proof step:</p>
          <table className={styles.table}>
            <thead>
              <tr><th>Rule</th><th>Law</th></tr>
            </thead>
            <tbody>
              <tr><td><code>BICONDITIONAL_EQUIVALENCE</code></td><td>A ↔ B = (A ∧ B) ∨ (¬A ∧ ¬B)</td></tr>
              <tr><td><code>DOUBLENEGATION_EQUIV</code></td><td>¬¬A = A</td></tr>
              <tr><td><code>DE_MORGAN</code></td><td>¬(A ∧ B) = ¬A ∨ ¬B &nbsp;·&nbsp; ¬(A ∨ B) = ¬A ∧ ¬B</td></tr>
              <tr><td><code>DISTRIBUTION</code></td><td>A ∧ (B ∨ C) = (A ∧ B) ∨ (A ∧ C)</td></tr>
              <tr><td><code>COMMUTATION</code></td><td>A ∧ B = B ∧ A &nbsp;·&nbsp; A ∨ B = B ∨ A</td></tr>
              <tr><td><code>ASSOCIATION</code></td><td>(A ∧ B) ∧ C = A ∧ (B ∧ C)</td></tr>
              <tr><td><code>COMPLEMENT</code></td><td>A ∧ ¬A = ⊥ &nbsp;·&nbsp; A ∨ ¬A = ⊤</td></tr>
              <tr><td><code>IDENTITY</code></td><td>A ∧ ⊤ = A &nbsp;·&nbsp; A ∨ ⊥ = A</td></tr>
              <tr><td><code>ANNIHILATION</code></td><td>A ∧ ⊥ = ⊥ &nbsp;·&nbsp; A ∨ ⊤ = ⊤</td></tr>
              <tr><td><code>INVERSE</code></td><td>¬⊤ = ⊥ &nbsp;·&nbsp; ¬⊥ = ⊤</td></tr>
              <tr><td><code>IDEMPOTENCE</code></td><td>A ∧ A = A &nbsp;·&nbsp; A ∨ A = A</td></tr>
              <tr><td><code>ABSORPTION</code></td><td>A ∨ (A ∧ B) = A</td></tr>
              <tr><td><code>REDUCTION</code></td><td>A ∧ (¬A ∨ B) = A ∧ B</td></tr>
              <tr><td><code>ADJACENCY</code></td><td>(A ∧ B) ∨ (A ∧ ¬B) = A</td></tr>
            </tbody>
          </table>
        </section>

        <footer className={styles.footer}>
          Puzzle source:{' '}
          <a href="http://philosophy.hku.hk/think/logic/knights.php" target="_blank" rel="noreferrer">
            philosophy.hku.hk
          </a>{' '}
          — licensed CC BY-SA 4.0
        </footer>

      </div>
    </div>
  );
}
