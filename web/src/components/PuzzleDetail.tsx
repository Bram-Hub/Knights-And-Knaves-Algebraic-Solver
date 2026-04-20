import { useState, useEffect } from 'react';
import type { PuzzleSummary, SolveResult } from '../types';
import { ProofSteps } from './ProofSteps';
import { Solution } from './Solution';
import { DownloadButton } from './DownloadButton';
import styles from './PuzzleDetail.module.css';

interface Props {
  puzzle: PuzzleSummary;
}

export function PuzzleDetail({ puzzle }: Props) {
  const [solution, setSolution] = useState<SolveResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/data/solutions/${puzzle.id}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`Solution not found (HTTP ${r.status})`);
        return r.json() as Promise<SolveResult>;
      })
      .then((data) => {
        setSolution(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [puzzle.id]);

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
        {!loading && !error && <DownloadButton puzzleId={puzzle.id} />}
        {loading && <span className={styles.solveHint}>Loading solution…</span>}
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
