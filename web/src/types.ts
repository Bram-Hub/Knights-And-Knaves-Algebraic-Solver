export interface Utterance {
  speaker: string;
  raw: string;
}

export interface PuzzleSummary {
  id: number;
  people: string[];
  utterances: Utterance[];
  solved: boolean;
}

export interface ProofStep {
  rule: string;
  description?: string;
  formula: string;
}

export type Assignment = Record<string, 'knight' | 'knave'>;

export interface SolveResult {
  id: number;
  people: string[];
  equivalence_steps: ProofStep[];
  symbol_map: Record<string, string>;
  assignments: Assignment[];
}
