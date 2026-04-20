import { useState } from 'react';
import type { PuzzleSummary } from '../types';
import styles from './PuzzleList.module.css';

interface Props {
  puzzles: PuzzleSummary[];
  selectedId: number | null;
  onSelect: (puzzle: PuzzleSummary) => void;
}

export function PuzzleList({ puzzles, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState('');

  const filtered = puzzles.filter((p) => {
    const q = query.toLowerCase();
    return (
      String(p.id).includes(q) ||
      p.people.some((name) => name.toLowerCase().includes(q))
    );
  });

  return (
    <div className={styles.container}>
      <input
        className={styles.search}
        type="text"
        placeholder="Search by puzzle # or name…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className={styles.list}>
        {filtered.map((p) => (
          <li
            key={p.id}
            className={`${styles.item} ${p.id === selectedId ? styles.selected : ''}`}
            onClick={() => onSelect(p)}
          >
            <span className={styles.puzzleId}>#{p.id}</span>
            <span className={styles.people}>{p.people.join(', ')}</span>
            {p.solved && <span className={styles.badge}>solved</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
