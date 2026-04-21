import type { ProofStep } from '../types';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function remap(formula: string, symbolMap: Record<string, string>): string {
  let mapped = formula;
  for (const person of Object.keys(symbolMap).sort((a, b) => b.length - a.length)) {
    mapped = mapped.replaceAll(`K_${person}`, symbolMap[person]);
  }
  return mapped;
}

export async function buildBramXml(
  puzzleId: number,
  steps: ProofStep[],
  symbolMap: Record<string, string>,
): Promise<string> {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

  const hashInput = new TextEncoder().encode(
    JSON.stringify({ id: puzzleId, steps }, Object.keys({ id: puzzleId, steps }).sort()),
  );
  const hashBuf = await crypto.subtle.digest('SHA-256', hashInput);
  const hashB64 = btoa(String.fromCharCode(...new Uint8Array(hashBuf)));

  const lines: string[] = [
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
    '<bram>',
    '  <program>Aris</program>',
    '  <version>0.1.0</version>',
    '  <metadata>',
    '    <author>mikehalpern</author>',
    `    <created>${now}</created>`,
    `    <modified>${now}</modified>`,
    `    <hash>${hashB64}</hash>`,
    '  </metadata>',
    '  <proof id="0">',
    '    <assumption linenum="0">',
    `      <raw>${escapeXml(remap(steps[0].formula, symbolMap))}</raw>`,
    '    </assumption>',
  ];

  let prevLine = 0;
  for (let i = 1; i < steps.length; i++) {
    const step = steps[i] as ProofStep & { premise?: number | null };
    lines.push(`    <step linenum="${i}">`);
    lines.push(`      <raw>${escapeXml(remap(step.formula, symbolMap))}</raw>`);
    lines.push(`      <rule>${escapeXml(step.rule)}</rule>`);
    const premise = step.premise ?? prevLine;
    if (premise != null) lines.push(`      <premise>${premise}</premise>`);
    lines.push('    </step>');
    prevLine = i;
  }

  lines.push(
    '    <goal>',
    `      <raw>${escapeXml(remap(steps[steps.length - 1].formula, symbolMap))}</raw>`,
    '    </goal>',
    '  </proof>',
    '</bram>',
    '',
  );

  return lines.join('\n');
}
