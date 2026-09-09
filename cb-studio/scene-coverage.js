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
      ${board.soundPlan?.length ? `<details><summary>Scene sound plan</summary>${board.soundPlan.map(s=>`<p><b>${esc(s.shotId)}</b> ${(s.cues||[]).map(c=>esc(`${c.timing}: ${c.instruction} (${c.destination})`)).join('<br>')}</p>`).join('')}</details>` : ''}
      <p class="dec-caption">Current camera and acting plan. Drawings and rendered outcomes are reviewed separately.</p><button type="button" class="btn ghost" data-coverage-play>Play timed plan</button><span data-coverage-status aria-live="polite"> Text plan only · picture and audio unverified</span>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">${units.flatMap(u => (u.panels || []).map(p => `<article data-duration="${esc(Number(u.duration)>0 ? Number(u.duration)/(u.panels.length||1) : 3)}" style="border:1px solid var(--line,#ddd);border-radius:8px;padding:14px;min-width:0">
        <small>${esc(u.shotId)} · VIEW ${esc(p.number)} ${p.timing ? '· ' + esc(p.timing) : ''}</small>
        <h4 style="margin:8px 0">${esc(p.entry)} · ${esc(p.framing)}</h4>
        <p>${esc(p.purpose)}</p>
        ${[['Viewpoint owner',p.viewpointOwner],['Camera',Object.entries(p.cinematography||{}).map(([k,v])=>`${k}: ${v}`).join('; ')],['Listening',p.listenerReaction],['Staging',p.staging],['Opening',p.startState],['Action',p.action],['Acting',p.performance],['Landing',p.endState],['Next view reveals',p.cutTo],['Why this cut',p.cutReason]].filter(([,v])=>v).map(([label,v])=>`<p style="overflow-wrap:anywhere"><b>${label}:</b> ${esc(v)}</p>`).join('')}
        </article>`)).join('')}</div></details>`;
  }
  function legacy(pkg) {
    return html({units:(pkg?.shots || []).map(s => ({shotId:s.shotId, panels:(s.storyboardInternalShotPlanApproved || []).map((v,i)=>({number:i+1,entry:v.transitionType||'view',framing:v.framingAndCamera,purpose:v.purpose,action:v.storyAction,performance:v.performanceFocus,staging:v.staging,startState:v.startState,endState:v.endState||v.landingImage,cutTo:v.cutTo,cutReason:v.cutReason,timing:v.timing}))}))});
  }
  let timer=null, active=null;
  globalThis.document?.addEventListener('click', event => {
    const button=event.target.closest('[data-coverage-play]');
    if(!button)return;
    if(timer){clearTimeout(timer);timer=null;}
    if(active){active.querySelectorAll('article').forEach(p=>p.style.outline='');active.querySelector('[data-coverage-play]').textContent='Play timed plan';}
    const board=button.closest('.studio-coverage');
    if(active===board){active=null;return;}
    active=board;button.textContent='Stop timed plan';
    const panels=[...board.querySelectorAll('article')];let index=0;
    function step(){
      if(!board.isConnected){active=null;return;}
      panels.forEach(p=>p.style.outline='');
      if(index>=panels.length){button.textContent='Play timed plan';active=null;timer=null;return;}
      const panel=panels[index++];panel.style.outline='3px solid #b48a48';
      board.querySelector('[data-coverage-status]').textContent=` View ${index}/${panels.length} · estimated timing · text only, no picture/audio review`;
      panel.scrollIntoView({block:'nearest',behavior:'smooth'});
      timer=setTimeout(step,Math.max(0.25,Number(panel.dataset.duration)||3)*1000);
    }
    step();
  });
  window.StudioCoverage = {html, legacy};
})();
