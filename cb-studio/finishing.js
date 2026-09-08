'use strict';
const episode = new URLSearchParams(location.search).get('episode') || 'Ep2';
let workspace;
let renderedHash;
const projectId = new URLSearchParams(location.search).get('projectId') || 'crystal-bears';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(s){const el=document.getElementById('message');el.hidden=false;el.textContent=s;}
async function call(action,extra={},route='/api/finishing'){
 const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectId,episode,action,masterSha256:workspace?.masterSha256,...extra})});
 const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;
}
async function refresh(){try{workspace=await call('status');render();}catch(e){message(e.message);}}
function mount(markup,retainedVideo){
 const content=document.getElementById('content'),template=document.createElement('template');template.innerHTML=markup;
 if(!retainedVideo){content.replaceChildren(template.content);return;}
 // A detached video reloads even if the same node is reinserted. Keep it and its
 // section connected while replacing the status controls around it.
 const section=retainedVideo.closest('section'),fresh=template.content.firstElementChild;
 for(const node of [...section.childNodes])if(node!==retainedVideo)node.remove();
 let before=true;
 for(const node of [...fresh.childNodes]){
  if(node.nodeName==='VIDEO'){before=false;continue;}
  section.insertBefore(node,before?retainedVideo:null);
 }
 fresh.remove();
 for(const node of [...content.childNodes])if(node!==section)node.remove();
 content.append(template.content);
}
function render(){
 document.getElementById('title').textContent=`${episode} · Final cut review`;
 if(!workspace.available||!workspace.finishingWorkflow){document.getElementById('content').textContent='No DaVinci review export has been registered for this episode.';return;}
 const f=workspace.finishingWorkflow,u=workspace.upscale,d=f.drive||{},approved=workspace.status==='approved';
 const receiptReady=d.verified===true&&d.masterSha256===workspace.masterSha256;
 const retainedVideo=renderedHash===workspace.masterSha256?document.querySelector('video'):null;
 const markup=`<section><div class="row"><b>${esc(f.version)}</b><span>${approved?'Signed off by Julian':workspace.verdict?.verdict==='rejected'?'Returned for repairs':'Awaiting your review'}</span><span>${Math.floor(workspace.durationSec/60)}m ${(workspace.durationSec%60).toFixed(1)}s · before enhancement</span></div><video controls preload="metadata" poster="${esc(f.posterUrl||'')}" src="${esc(workspace.masterUrl)}"></video><p>${receiptReady?`<a class="button" href="${esc(d.url)}" target="_blank" rel="noopener">Watch this cut on Google Drive</a>`:'Google Drive upload verification pending.'}</p><small class="muted">Exact review file: ${esc(workspace.masterSha256)}</small></section>
 <section><h2>Director’s review</h2><p>Watch the whole cut for the story and reactions, then inspect cut boundaries, character continuity, colour, dialogue, music and the ending.</p>${(f.findings||[]).map(x=>`<p class="issue"><button data-seek="${Number(x.seconds)}">${esc(x.timecode)}</button> ${esc(x.note)} <b>${esc(x.status)}</b></p>`).join('')}<p class="muted">${esc(f.audioNote)}</p><button id="resolve">Check current DaVinci timeline</button><button id="brief">Show director and post-supervisor brief</button><pre id="inspection" hidden></pre></section>
 <section><h2>Your decision on this exact cut</h2><label for="note">Review notes / requested repairs</label><textarea id="note" placeholder="Describe any changes, ideally with timecodes."></textarea><button id="approve" ${!receiptReady?'disabled':''}>Sign off this cut</button><button id="reject">Return for repairs</button><p class="muted">Sign-off records this file version. Replacing the cut requires a new sign-off. It does not start or pay for enhancement.</p>${workspace.verdict?`<p>Last decision: ${esc(workspace.verdict.verdict)} · ${esc(workspace.verdict.note)}</p>`:''}</section>
 <section><h2>4K enhancement · BytePlus vCube</h2><p>${esc(u.settings)}</p><p>${approved?'Cut sign-off recorded.':'Locked until you sign off this cut.'}</p>${u.missing.length?`<p class="muted">Connection setup pending: ${esc(u.missing.join(', '))}. Uses the Studio’s existing secure configuration.</p>`:`<p>Estimated processing: $${u.estimatedUsd} USD, excluding tax, storage and transfer.</p><label>Processing allowance $ <input id="allowance" type="number" min="${u.estimatedUsd}" step="0.01" value="${Math.ceil(u.estimatedUsd*100)/100}"></label>`}<button id="upscale" ${!u.canStart?'disabled':''}>Start vCube enhancement</button>${u.job?`<p>Job: ${esc(u.job.status)}</p>${u.job.runId?'<button id="poll">Check enhancement progress</button>':''}`:''}<p class="muted">The enhanced result needs picture, duration, colour and audio checks before delivery. Provider completion is not final sign-off.</p></section>`;
 mount(markup,retainedVideo);
 renderedHash=workspace.masterSha256;
 window.StudioDrafts?.bind(document.getElementById('note'),[projectId,episode,'finishing',workspace.masterSha256,'note'],{revision:workspace.masterSha256});
 document.querySelectorAll('[data-seek]').forEach(b=>b.onclick=()=>{document.querySelector('video').currentTime=Number(b.dataset.seek);});
 document.getElementById('approve').onclick=()=>decision('approve');document.getElementById('reject').onclick=()=>decision('reject');
 for(const [id,action] of [['resolve','resolve'],['brief','director-brief']])document.getElementById(id).onclick=async()=>{try{message('Reading…');const result=await call(action);const box=document.getElementById('inspection');box.hidden=false;box.textContent=action==='resolve'?`Resolve: ${result.product} ${result.version}\nProject: ${result.project} (${result.projectId||'ID unavailable'})\nTimeline: ${result.timeline} (${result.timelineId||'ID unavailable'})\nFrame rate: ${result.frameRate}\nDuration: ${result.endFrame-result.startFrame} frames\nReview markers: ${Object.keys(result.markers||{}).length}\n\nCandidate binding: ${result.binding?.status||'unbound'}\n${result.binding?.message||'No candidate match has been established.'}`:`${result.instruction}\n\nReview dimensions:\n${result.dimensions.map(x=>'• '+x).join('\n')}\n\nDirector contract:\n${result.directorContract.trim()}\n\nPost Supervisor contract:\n${result.postSupervisorContract.trim()}\n\nOperational references:\n${Object.entries(result.postSupervisorReferences||{}).map(([name,text])=>name+'\n'+text).join('\n\n')}`;message(action==='resolve'?'Resolve state read. No edits made.':'Review brief prepared; this does not claim a completed visual review.');}catch(e){message(e.message);}};
 document.getElementById('upscale').onclick=async()=>{try{message('Submitting the approved enhancement request…');await call('upscale',{maxCostUsd:Number(document.getElementById('allowance').value)});await refresh();message('Enhancement request recorded. Check the job status below.');}catch(e){message(e.message);}};
 document.getElementById('poll')?.addEventListener('click',async()=>{try{await call('poll');await refresh();}catch(e){message(e.message);}});
}
async function decision(action){const note=document.getElementById('note'),clear=window.StudioDrafts?.capture(note);try{await call(action,{note:note.value,reviewer:'Julian'},'/api/post-workspace');clear?.();await refresh();message(action==='approve'?'Your sign-off is recorded for this exact file. Enhancement has not started.':'Returned for repairs. Your notes are saved.');}catch(e){message(e.message);}}
refresh();
