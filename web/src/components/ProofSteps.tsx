import { useState } from 'react';
import type { ProofStep } from '../types';
import styles from './ProofSteps.module.css';

const PREVIEW = 5;

const PHASE_MAP: Record<string, number> = {
  START: 1,
  BICONDITIONAL_EQUIVALENCE: 2,
  DOUBLENEGATION_EQUIV: 3,
  DE_MORGAN: 3,
};

const PHASE_LABELS: Record<number, string> = {
  1: 'Phase 1 — Encode',
  2: 'Phase 2 — Eliminate biconditionals',
  3: 'Phase 3 — Negation Normal Form',
  4: 'Phase 4 — Distribute to DNF',
};

const PHASE_COLORS: Record<number, string> = {
  1: '#1a2e1a',
  2: '#261a3a',
  3: '#3a2415',
  4: '#0d1f33',
};

function getPhase(rule: string): number {
  return PHASE_MAP[rule] ?? 4;
}

interface Props {
  steps: ProofStep[];
  symbolMap: Record<string, string>;
}

export function ProofSteps({ steps }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showPhases, setShowPhases] = useState(false);

  const visible = expanded ? steps : steps.slice(0, PREVIEW);

  const rows: React.ReactNode[] = [];
  visible.forEach((step, i) => {
    const phase = getPhase(step.rule);
    const prevPhase = i > 0 ? getPhase(visible[i - 1].rule) : null;
    if (showPhases && (i === 0 || phase !== prevPhase)) {
      rows.push(
        <li
          key={`divider-${i}`}
          className={styles.phaseDivider}
          style={{ background: PHASE_COLORS[phase] }}
        >
          {PHASE_LABELS[phase]}
        </li>,
      );
    }
    rows.push(
      <li key={i} className={styles.step}>
        <span className={styles.rule}>{step.rule}</span>
        <code className={styles.formula}>{step.formula}</code>
      </li>,
    );
  });

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span>Proof steps ({steps.length} total)</span>
        <button
          className={`${styles.phaseToggle} ${showPhases ? styles.phaseToggleActive : ''}`}
          onClick={() => setShowPhases((p) => !p)}
        >
          {showPhases ? 'Hide phases' : 'Show phases'}
        </button>
      </div>
      <ol className={styles.list}>{rows}</ol>
      {steps.length > PREVIEW && (
        <button className={styles.toggle} onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'Show less' : `Show all ${steps.length} steps`}
        </button>
      )}
    </div>
  );
}
