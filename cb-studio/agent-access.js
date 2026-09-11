/* MCP setup and workflow evidence share the authenticated Studio API. */
(() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function get(path) {
    const response = await fetch(path, {cache:'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Studio request failed');
    return data;
  }
  window.openAgentAccess = async () => {
    const modal = document.getElementById('modal'), sheet = document.getElementById('sheet');
    modal.classList.add('show');
    sheet.innerHTML = '<button class="x" aria-label="Close" onclick="document.getElementById(\'modal\').classList.remove(\'show\')">×</button><h2>Agent access</h2><p role="status">Loading connection details…</p>';
    try {
      const info = await get('/api/agent-access');
      sheet.innerHTML = `<button class="x" aria-label="Close" onclick="document.getElementById('modal').classList.remove('show')">×</button><h2>Direct this Studio from an assistant</h2>
        <p>The Studio agent and connected assistants use the same production APIs, approvals, budgets and jobs. Keep the Studio running while work is in progress.</p>
        <h3>Local MCP connection</h3><p>Use this configuration in a client that supports local MCP. Provider keys stay in Workspace connections.</p>
        <pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(info.config, null, 2))}</pre>
        <p>${esc(info.remote)}</p><p>Connection details do not mean an external assistant has been connected or tested.</p>
        <details><summary>Production command guide</summary><pre style="white-space:pre-wrap">${esc(info.instructions)}</pre></details>
        <h3>Workflow improvements</h3><p>A workaround is not a verified fix. Each record tracks the cause, shared change and validation evidence.</p><div id="agent-incidents"></div>`;
      const project = typeof CURRENT_PROJECT !== 'undefined' ? CURRENT_PROJECT : null;
      const el = sheet.querySelector('#agent-incidents');
      if (!project) { el.textContent = 'Open a project to review its workflow incidents.'; return; }
      const data = await get('/api/workflow-incidents?projectId=' + encodeURIComponent(project.id));
      el.innerHTML = data.incidents.length ? data.incidents.map(x => `<details><summary>${esc(x.summary)} · ${esc(x.status)}</summary><p>${esc(x.observed)}</p><p>Shared component: ${esc(x.affectedComponent || 'Not diagnosed')}</p><p>Regression: ${esc(x.regressionEvidence || 'Not recorded')}</p><p>Workflow check: ${esc(x.workflowEvidence || 'Not recorded')}</p></details>`).join('') : '<p>No workflow incidents recorded for this project.</p>';
    } catch (e) { const p = document.createElement('p'); p.setAttribute('role','alert'); p.textContent = e.message; sheet.append(p); }
  };
})();
