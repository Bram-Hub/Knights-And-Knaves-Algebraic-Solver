import { useEffect, useState } from 'react';
import type { PuzzleSummary } from './types';
import { PuzzleList } from './components/PuzzleList';
import { PuzzleDetail } from './components/PuzzleDetail';
import { LandingPage } from './components/LandingPage';
import styles from './App.module.css';

export default function App() {
  const [puzzles, setPuzzles] = useState<PuzzleSummary[]>([]);
  const [selected, setSelected] = useState<PuzzleSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/data/puzzles.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<PuzzleSummary[]>;
      })
      .then((data) => {
        setPuzzles(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <button className={styles.logo} onClick={() => setSelected(null)}>
            Knights &amp; Knaves
          </button>
          {!loading && (
            <span className={styles.count}>{puzzles.length} puzzles</span>
          )}
        </div>
        {loading && <p className={styles.status}>Loading…</p>}
        {error && <p className={styles.statusError}>{error}</p>}
        {!loading && !error && (
          <PuzzleList
            puzzles={puzzles}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        )}
      </aside>
      <main className={styles.main}>
        {selected ? (
          <PuzzleDetail key={selected.id} puzzle={selected} />
        ) : (
          <LandingPage />
        )}
      </main>
    </div>
  );
}
