/* A read-only view of production direction. This never authors a second plan. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function html(board) {
    const units = board?.units || [];
    const count = units.reduce((n, u) => n + (u.panels?.length || 0), 0);
    if (!count) return '';
    return `<details class="studio-coverage sp-box" data-coverage-revision="${esc(board.revision || '')}"><summary>Scene storyboard · ${count} planned views</summary>
      ${board.audienceJourney ? `<p>${esc(board.audienceJourney)}</p>` : ''}
      <p class="dec-caption">Current camera and acting plan. Drawings and rendered outcomes are reviewed separately.</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">${units.flatMap(u => (u.panels || []).map(p => `<article style="border:1px solid var(--line,#ddd);border-radius:8px;padding:14px;min-width:0">
        <small>${esc(u.shotId)} · VIEW ${esc(p.number)} ${p.timing ? '· ' + esc(p.timing) : ''}</small>
        <h4 style="margin:8px 0">${esc(p.entry)} · ${esc(p.framing)}</h4>
        <p>${esc(p.purpose)}</p>
        ${[['Staging',p.staging],['Opening',p.startState],['Action',p.action],['Acting',p.performance],['Landing',p.endState],['Next view reveals',p.cutTo],['Why this cut',p.cutReason]].filter(([,v])=>v).map(([label,v])=>`<p style="overflow-wrap:anywhere"><b>${label}:</b> ${esc(v)}</p>`).join('')}
        </article>`)).join('')}</div></details>`;
  }
  function legacy(pkg) {
    return html({units:(pkg?.shots || []).map(s => ({shotId:s.shotId, panels:(s.storyboardInternalShotPlanApproved || []).map((v,i)=>({number:i+1,entry:v.transitionType||'view',framing:v.framingAndCamera,purpose:v.purpose,action:v.storyAction,performance:v.performanceFocus,staging:v.staging,startState:v.startState,endState:v.endState||v.landingImage,cutTo:v.cutTo,cutReason:v.cutReason,timing:v.timing}))}))});
  }
  window.StudioCoverage = {html, legacy};
})();
