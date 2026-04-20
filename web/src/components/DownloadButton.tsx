import { useState } from 'react';
import { IS_STATIC } from '../config';
import styles from './DownloadButton.module.css';

interface Props {
  puzzleId: number;
}

type State = 'idle' | 'loading' | 'done';

export function DownloadButton({ puzzleId }: Props) {
  const [state, setState] = useState<State>('idle');

  async function handleClick() {
    setState('loading');
    try {
      const res = await fetch(IS_STATIC ? `/data/bram/${puzzleId}.bram` : `/api/bram/${puzzleId}`);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
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
