import { useState } from 'react';
import type { SolveResult } from '../types';
import { IS_STATIC } from '../config';
import { buildBramXml } from '../utils/bramGenerator';
import styles from './DownloadButton.module.css';

interface Props {
  puzzleId: number;
  solution?: SolveResult;
}

type State = 'idle' | 'loading' | 'done';

export function DownloadButton({ puzzleId, solution }: Props) {
  const [state, setState] = useState<State>('idle');

  async function handleClick() {
    setState('loading');
    try {
      let blob: Blob;
      if (IS_STATIC && solution) {
        const xml = await buildBramXml(puzzleId, solution.equivalence_steps, solution.symbol_map);
        blob = new Blob([xml], { type: 'application/octet-stream' });
      } else {
        const res = await fetch(`/api/bram/${puzzleId}`);
        if (!res.ok) throw new Error('Download failed');
        blob = await res.blob();
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `puzzle_${puzzleId}.bram`;
      a.click();
      URL.revokeObjectURL(url);
      setState('done');
      setTimeout(() => setState('idle'), 3000);
    } catch {
      setState('idle');
    }
  }

  const label =
    state === 'loading' ? 'Generating…' : state === 'done' ? 'Downloaded!' : 'Download .bram';

  return (
    <button
      className={`${styles.btn} ${styles[state]}`}
      onClick={handleClick}
      disabled={state === 'loading'}
    >
      {label}
    </button>
  );
}
