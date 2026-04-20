import { useState } from 'react';
import type { ProofStep } from '../types';
import styles from './ProofSteps.module.css';

const PREVIEW = 5;

interface Props {
  steps: ProofStep[];
  symbolMap: Record<string, string>;
}

export function ProofSteps({ steps, symbolMap }: Props) {
  const [expanded, setExpanded] = useState(false);

  const legend = Object.entries(symbolMap)
    .map(([name, letter]) => `${letter} = ${name}`)
    .join('  ·  ');

  const visible = expanded ? steps : steps.slice(0, PREVIEW);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span>Proof steps ({steps.length} total)</span>
        {legend && <span className={styles.legend}>{legend}</span>}
      </div>
      <ol className={styles.list}>
        {visible.map((step, i) => (
          <li key={i} className={styles.step}>
            <span className={styles.rule}>{step.rule}</span>
            <code className={styles.formula}>{step.formula}</code>
          </li>
        ))}
      </ol>
      {steps.length > PREVIEW && (
        <button className={styles.toggle} onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'Show less' : `Show all ${steps.length} steps`}
        </button>
      )}
    </div>
  );
}
