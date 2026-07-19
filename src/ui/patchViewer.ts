export type PatchPreview = {
  pythonDiff: string;
  jsonDiff: string;
  kiCadDiff: string;
  summary: string;
};

export function renderPatchPreview(patch: PatchPreview): string {
  return [
    'Patch Summary:',
    patch.summary,
    '\nPython Diff:',
    patch.pythonDiff,
    '\nJSON Diff:',
    patch.jsonDiff,
    '\nKiCad Diff:',
    patch.kiCadDiff
  ].join('\n');
}
