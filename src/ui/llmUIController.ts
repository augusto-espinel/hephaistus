import * as vscode from 'vscode';

/**
 * Lightweight UI controller for LLM-driven optimization in VS Code.
 * Provides a streaming view of LLM output and patch previews with basic accept/reject actions.
 */
export class LlmUIController {
  private panel?: vscode.WebviewPanel;

  constructor(private context: vscode.ExtensionContext) {}

  public openUI(): void {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.One);
      return;
    }
    this.panel = vscode.window.createWebviewPanel(
      'hephaistus.llmUI',
      'HephAIstus: LLM Optimization',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true
      }
    );

    this.panel.webview.html = this.buildHtml();

    this.panel.webview.onDidReceiveMessage((message) => {
      if (!message?.type) return;
      switch (message.type) {
        case 'acceptPatch':
          // In a full implementation, this would trigger patch application path.
          vscode.window.showInformationMessage('Patch accepted (UI placeholder).');
          break;
        case 'rejectPatch':
          vscode.window.showInformationMessage('Patch rejected (UI placeholder).');
          break;
      }
    }, undefined, this.context.subscriptions);
  }

  // Stream output into the UI (if panel is open)
  public streamOutput(text: string): void {
    this.panel?.webview.postMessage({ type: 'stream', value: text });
  }

  private buildHtml(): string {
    // Minimal inline UI; in a real setup, this would load a bundled web UI.
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline' 'self'">
  <title>LLM Optimization</title>
</head>
<body>
  <h2>LLM-Driven Optimization</h2>
  <div id="stream" style="border:1px solid #ccc; height:180px; overflow:auto; padding:8px;">
    <em>LLM output will appear here as streaming text.</em>
  </div>
  <h3>Patch Preview</h3>
  <pre id="patch" style="background:#f6f6f6; border:1px solid #ddd; padding:8px; height:180px; overflow:auto;"></pre>
  <button id="accept" style="margin-right:8px;">Accept Patch</button>
  <button id="reject">Reject Patch</button>
  <script>
    const vscode = acquireVsCodeApi();
    window.addEventListener('message', event => {
      const msg = event.data;
      if (msg?.type === 'stream') {
        const el = document.getElementById('stream');
        if (el) { el.textContent += '\n' + msg.value; el.scrollTop = el.scrollHeight; }
      }
    });
    document.getElementById('accept').onclick = () => vscode.postMessage({ type:'acceptPatch' });
    document.getElementById('reject').onclick = () => vscode.postMessage({ type:'rejectPatch' });
  </script>
</body>
</html>`;
  }
}
