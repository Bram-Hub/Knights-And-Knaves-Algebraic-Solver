import type { Assignment } from '../types';
import styles from './Solution.module.css';

interface Props {
  people: string[];
  assignments: Assignment[];
}

export function Solution({ people, assignments }: Props) {
  if (assignments.length === 0) {
    return (
      <div className={styles.box}>
        <div className={styles.label}>Solution</div>
        <p className={styles.none}>No consistent assignment exists — the puzzle has no solution.</p>
      </div>
    );
  }

  return (
    <div className={styles.box}>
      <div className={styles.label}>
        Solution{assignments.length > 1 ? ` (${assignments.length} possibilities)` : ''}
      </div>
      {assignments.map((assignment, i) => (
        <div key={i} className={styles.assignment}>
          {assignments.length > 1 && (
            <span className={styles.caseNum}>Case {i + 1}:</span>
          )}
          <div className={styles.roles}>
            {people.map((person) => {
              const role = assignment[person];
              return (
                <span key={person} className={`${styles.role} ${styles[role]}`}>
                  <span className={styles.person}>{person}</span>
                  <span className={styles.roleName}>{role}</span>
                </span>
              );
            })}
          </div>
          <p className={styles.sentence}>
            {people.map((person, idx) => {
              const role = assignment[person];
              const isLast = idx === people.length - 1;
              const sep = isLast ? '.' : idx === people.length - 2 ? ', and ' : ', ';
              return (
                <span key={person}>
                  <strong>{person}</strong> is a {role}{sep}
                </span>
              );
            })}
          </p>
        </div>
      ))}
    </div>
  );
}
