export let currentUiController: any = null;
export function setUiController(ctrl: any) {
  currentUiController = ctrl;
}
export function streamToUi(text: string) {
  currentUiController?.streamOutput(text);
}
export function patchPreviewToUi(patch: string) {
  currentUiController?.streamOutput(`PATCH_PREVIEW:${patch}`);
}
export function showUiMessage(msg: string) {
  currentUiController?.streamOutput(`UI_MSG:${msg}`);
}

// Pending patch flow for UI-driven approval
let _pendingPatch: string | null = null;
export function setPendingPatch(patch: string) {
  _pendingPatch = patch;
}
export function getPendingPatch(): string | null {
  return _pendingPatch;
}
export function clearPendingPatch(): void {
  _pendingPatch = null;
}
