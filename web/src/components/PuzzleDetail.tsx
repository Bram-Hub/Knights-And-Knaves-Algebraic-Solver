import { useState, useEffect } from 'react';
import type { PuzzleSummary, SolveResult } from '../types';
import { ProofSteps } from './ProofSteps';
import { Solution } from './Solution';
import { DownloadButton } from './DownloadButton';
import styles from './PuzzleDetail.module.css';

interface Props {
  puzzle: PuzzleSummary;
}

async function fetchSolution(puzzleId: number): Promise<SolveResult> {
  const res = await fetch(`/api/solve/${puzzleId}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const data = await res.json();

  if (data.status === 'done') return data as SolveResult;

  // Poll until done
  while (true) {
    await new Promise((r) => setTimeout(r, 600));
    const poll = await fetch(`/api/solve/${puzzleId}/status`);
    if (!poll.ok) throw new Error(`Poll error ${poll.status}`);
    const status = await poll.json();
    if (status.status === 'done') return status as SolveResult;
    if (status.status === 'error') throw new Error(status.detail ?? 'Solver error');
  }
}

export function PuzzleDetail({ puzzle }: Props) {
  const [solution, setSolution] = useState<SolveResult | null>(null);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (puzzle.solved) handleSolve();
  }, []);

  async function handleSolve() {
    setSolving(true);
    setError(null);
    try {
      const data = await fetchSolution(puzzle.id);
      setSolution(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setSolving(false);
    }
  }

  const isSolved = puzzle.solved || solution != null;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Puzzle #{puzzle.id}</h2>
        <div className={styles.people}>
          {puzzle.people.map((p) => (
            <span key={p} className={styles.personBadge}>{p}</span>
          ))}
        </div>
      </div>

      <div className={styles.utterances}>
        {puzzle.utterances.map((u, i) => (
          <div key={i} className={styles.utterance}>
            <span className={styles.speaker}>{u.speaker}</span>
            <span className={styles.says}>says:</span>
            <span className={styles.statement}>"{u.raw}"</span>
          </div>
        ))}
      </div>

      <div className={styles.actions}>
        {!isSolved && (
          <button className={styles.solveBtn} onClick={handleSolve} disabled={solving}>
            {solving ? <span className={styles.spinner}>Solving…</span> : 'Solve'}
          </button>
        )}
        {isSolved && (
          <>
            {!solution && (
              <button className={styles.solveBtn} onClick={handleSolve} disabled={solving}>
                {solving ? <span className={styles.spinner}>Solving…</span> : 'Re-solve'}
              </button>
            )}
            <DownloadButton puzzleId={puzzle.id} />
          </>
        )}
        {solving && (
          <span className={styles.solveHint}>
            {puzzle.people.length >= 3
              ? 'Complex puzzle — may take a few seconds…'
              : ''}
          </span>
        )}
        {error && <span className={styles.error}>{error}</span>}
      </div>

      {solution && (
        <>
          <Solution people={solution.people} assignments={solution.assignments} />
          <ProofSteps
            steps={solution.equivalence_steps}
            symbolMap={solution.symbol_map}
          />
        </>
      )}
    </div>
  );
}
