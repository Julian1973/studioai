/* Director's board, continuity inspector and episode review. All writes use the shared command dispatcher. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const url = record => BASE + '/' + record.path.split('/').map(encodeURIComponent).join('/');
  const clock = n => `${Math.floor((n || 0) / 60)}:${Math.floor((n || 0) % 60).toString().padStart(2,'0')}`;
  const cost = n => n == null ? 'Set service estimates' : `$${Number(n).toFixed(2)} estimated`;
  const labels = {preparing:'Preparing', ready_for_review:'Ready for review', approved:'Approved', needs_attention:'Needs attention', missing:'To prepare'};
  let active;
  function mount(ctx, send, draw) {
    active = ctx; ctx.reviewSend = send; ctx.reviewDraw = draw; ctx.mode = window.StudioJourney?'shot':'board'; ctx.boardFilter = 'all';
    const before = ctx.root.querySelector('.sp-desk');
    if (!before) return;
    before.insertAdjacentHTML('beforebegin', `<nav class="sp-workflow" aria-label="Production workspace"><button data-view="board" class="btn">Episode board</button><button data-view="shot" class="btn ghost">Shot workspace</button><button data-view="review" class="btn ghost">Review episode</button></nav><section id="sp-summary" aria-label="Production readiness"></section><section id="sp-board"></section><section id="sp-timeline" hidden></section>`);
    ctx.root.querySelector('#sp-outcome').insertAdjacentHTML('beforebegin','<div id="sp-proposal"></div>');
    ctx.root.querySelector('#sp-outcome').insertAdjacentHTML('afterend','<section id="sp-continuity"></section>');
    ctx.root.querySelector('.sp-workflow').onclick = e => {const b=e.target.closest('[data-view]');if(b)show(ctx,b.dataset.view);};
    ctx.root.querySelector('#sp-board').onclick = e => {
      const shot=e.target.closest('[data-open-shot]'),filter=e.target.closest('[data-filter]'),task=e.target.closest('[data-task]');
      if(shot)select(ctx,shot.dataset.openShot);
      if(filter){ctx.boardFilter=filter.dataset.filter;paintBoard(ctx);}
      if(task?.dataset.task==='continue'){const row=ctx.snapshot.review.shots.find(s=>!s.approved);if(row)select(ctx,row.id);else show(ctx,'review');}
      if(task?.dataset.task==='repair'){ctx.boardFilter='needs_attention';paintBoard(ctx);}
    };
    ctx.root.querySelector('#sp-proposal').onclick = e => {
      const b=e.target.closest('[data-edit]');if(!b)return;
      const shot=ctx.snapshot.state.shots.find(s=>s.id===ctx.shotId);
      send(ctx,b.dataset.edit,{proposalId:shot?.proposal?.id,prepare:!window.StudioJourney&&b.dataset.edit==='apply_revision'});
    };
    ctx.root.querySelector('#sp-continuity').onclick = e => {
      const reference=e.target.closest('[data-reference-choice]');
      if(reference){
        const shot=ctx.snapshot.state.shots.find(s=>s.id===ctx.shotId), choices=ctx.snapshot.review.inspections[shot.id].suggestions;
        const choice=reference.dataset.referenceChoice;
        send(ctx,'choose_reference',{reference:choice==='clear'?null:choices[Number(choice)]?.choice,cameraSetupId:ctx.root.querySelector('#sp-camera-setup').value});return;
      }
      if(e.target.closest('[data-media-review]')){send(ctx,'media_review');return;}
      const cleanup=e.target.closest('[data-cleanup-review]');
      if(cleanup){send(ctx,'cleanup_review_uploads',{jobId:cleanup.dataset.cleanupReview});return;}
      const finding=e.target.closest('[data-review-finding]');
      if(finding){
        const report=ctx.snapshot.review.inspections[ctx.shotId].mediaReviews.find(r=>r.id===finding.dataset.report&&r.current);
        if(!report)return;
        const item=report.findings[Number(finding.dataset.reviewFinding)],input=ctx.root.querySelector('#sp-direction');
        const proposal=`At ${item.seconds}s: ${item.observation}\nDirection to consider: ${item.suggestion}`;
        input.value=input.value.trim()?input.value+'\n\n'+proposal:proposal;
        window.StudioDrafts?.save(input);input.focus();return;
      }
      const b=e.target.closest('[data-bind-states]');if(!b)return;
      const bindings=[...ctx.root.querySelectorAll('[data-character-state]')].filter(el=>el.value).map(el=>({character:el.dataset.characterState,stateId:el.value}));
      send(ctx,'bind_states',{characterStates:bindings});
    };
    ctx.root.querySelector('#sp-timeline').onclick = e => timelineClick(ctx,e);
    show(ctx,window.StudioJourney?'shot':'board');
  }
  function show(ctx,mode){
    if(!ctx?.root?.querySelector('#sp-board'))return;
    if(ctx.mode==='review'&&mode!=='review')ctx.root.querySelector('#sp-episode-player')?.pause();
    ctx.mode=mode;
    ctx.root.querySelector('#sp-board').hidden=mode!=='board';
    ctx.root.querySelector('.sp-desk').hidden=mode!=='shot';
    ctx.root.querySelector('#sp-timeline').hidden=mode!=='review';
    for(const button of ctx.root.querySelectorAll('[data-view]')){button.classList.toggle('ghost',button.dataset.view!==mode);button.setAttribute('aria-current',button.dataset.view===mode?'page':'false');}
    if(ctx.snapshot?.review)paint(ctx);
  }
  function select(ctx,id){ctx.shotId=id;ctx.signature='';ctx.reviewDraw(ctx);show(ctx,'shot');}
  function paint(ctx){
    if(!ctx.snapshot?.review)return;
    const summary=ctx.snapshot.review.summary;
    ctx.root.querySelector('#sp-summary').innerHTML=`<div><strong>${clock(summary.approvedSeconds)}</strong><span>Approved footage</span></div><div><strong>${summary.approvedShots} / ${summary.shots}</strong><span>Shots approved · ${summary.generatedShots} generated</span></div><div><strong>${summary.approvedVoices} / ${summary.voiceShots}</strong><span>Voice performances approved</span></div><div><strong>${summary.blockers + summary.joinReviews}</strong><span>Blockers & joins to review</span></div>`;
    paintBoard(ctx);paintShot(ctx);paintTimeline(ctx);
  }
  function paintBoard(ctx){
    const view=ctx.snapshot.review, board=ctx.root.querySelector('#sp-board');
    board.innerHTML=`<div class="sp-board-head"><div><h3>Your episode, scene by scene</h3><p>Review the next outcome or open any shot to give direction.</p><p>${cost(view.summary.remainingEstimateUsd)} to prepare missing outcomes.</p><small>${esc(view.summary.forecastMeaning)}</small></div><div class="sp-actions"><button class="btn" data-task="continue">Continue episode</button><button class="btn ghost" data-task="repair">Find shots to repair</button></div></div><div class="sp-filters" role="group" aria-label="Filter shots">${[['all','All shots'],['ready_for_review','Ready for review'],['needs_attention','Needs attention'],['approved','Approved'],['missing','To prepare']].map(([id,label])=>`<button class="btn ${ctx.boardFilter===id?'':'ghost'}" data-filter="${id}" aria-pressed="${ctx.boardFilter===id}">${label}</button>`).join('')}</div>${view.scenes.map(scene=>{
      const rows=scene.shots.filter(s=>ctx.boardFilter==='all'||s.status===ctx.boardFilter);
      if(!rows.length)return '';
      return `<section class="sp-scene"><header><h3>Scene ${scene.number}</h3><p>${scene.approved} / ${scene.shots.length} approved · ${clock(scene.approvedSeconds)} footage · ${cost(scene.remainingEstimateUsd)} remaining</p></header><div class="sp-shot-grid">${rows.map(s=>`<button class="sp-shot-card ${s.status}" data-open-shot="${esc(s.id)}"><div class="sp-thumb">${s.thumbnail?`<img loading="lazy" src="${esc(url(s.thumbnail))}" alt="${esc(s.title)}">`:`<span>${s.stage==='archive'?'Preserved record':'Awaiting keyframe'}</span>`}<span class="sp-status">${labels[s.status]}</span></div><div class="sp-shot-copy"><small>${esc(s.id)} · ${s.plannedSeconds}s planned</small><strong>${esc(s.title)}</strong><span>${s.stage==='done'?'Watch approved':s.stage==='archive'?'Production archive':s.stage==='request'?'Review render request':s.stage.toUpperCase()}${s.issueCount?` · ${s.issueCount} review ${s.issueCount===1?'note':'notes'}`:''}</span></div></button>`).join('')}</div></section>`;
    }).join('') || '<div class="sp-box"><h3>No shots in this view yet</h3><p>Save a script and approve an episode allowance to prepare directed shots, or choose another filter.</p></div>'}`;
  }
  function paintShot(ctx){
    const shot=ctx.snapshot.state.shots.find(s=>s.id===ctx.shotId),root=ctx.root;
    if(!shot)return;
    const proposal=shot.proposal, editSignature=JSON.stringify([shot.id,proposal,shot.editHistory?.length]);
    const node=root.querySelector('#sp-proposal');
    if(node.dataset.signature!==editSignature){
      node.dataset.signature=editSignature;
      node.innerHTML=proposal?`<section class="sp-proposal sp-box"><span class="lab">Proposed direction · ${esc(shot.id)}</span><h3>Review what will change</h3><p>${esc(proposal.message)}</p><p>Replaces: ${esc(proposal.impact.reset.map(s=>s.toUpperCase()).join(', ')||'No outcomes')}. Preserves: ${esc(proposal.impact.preserved.map(s=>s.toUpperCase()).join(', ')||'Existing version history')}.</p>${proposal.impact.diff.map(d=>`<details><summary>${esc(d.field)}</summary><div class="sp-diff"><div><small>Current</small><pre>${esc(typeof d.before==='string'?d.before:JSON.stringify(d.before,null,2))}</pre></div><div><small>Proposed</small><pre>${esc(typeof d.after==='string'?d.after:JSON.stringify(d.after,null,2))}</pre></div></div></details>`).join('')}<p>Other shots retain their approved files. Neighbouring joins will be flagged for review.</p><div class="sp-actions"><button class="btn" data-edit="apply_revision">${window.StudioJourney?'Apply correction':'Apply & prepare'}</button><button class="btn ghost" data-edit="discard_revision">Keep current version</button></div></section>`:shot.editHistory?.length?'<button class="btn ghost" data-edit="undo_revision">Undo last direction edit</button>':'';
    }
    const inspection=ctx.snapshot.review.inspections[shot.id];
    const inspector=root.querySelector('#sp-continuity'), signature=JSON.stringify([shot.id,inspection,ctx.snapshot.characterStates,shot.characterStates,ctx.snapshot.services.review,shot.outcomes?.watch?.id,shot.outcomes?.watch?.status,shot.cameraSetupId,shot.compositionReference]);
    if(inspector.dataset.signature===signature)return;
    inspector.dataset.signature=signature;
    const rawRefs=inspection.actualReferences.length?inspection.actualReferences:inspection.references, unique=new Map();
    for(const ref of rawRefs){const key=JSON.stringify([ref.path,ref.hash,ref.role]);if(unique.has(key)){const old=unique.get(key);old.usedFor=[...new Set([old.usedFor,ref.usedFor].filter(Boolean))].join(' / ');}else unique.set(key,{...ref});}
    const refs=[...unique.values()];
    const figure=r=>`<figure><img loading="lazy" src="${esc(url(r))}" alt="${esc(r.name)}"><figcaption><strong>${esc(r.name)}</strong><span>${esc(r.role||'Generation reference')}</span><span>${esc(r.approvalStatus||'Supplied')} · ${esc(r.usedFor?.toUpperCase()||'Next input')}</span><small>Version ${esc((r.version||r.hash||'').slice(0,12))}</small></figcaption></figure>`;
    inspector.innerHTML=`<div class="sp-box"><h3>References & continuity</h3><p>${esc(shot.transition==='continuation'?'Continue from the preceding approved ending.':'Cut to this shot’s own opening composition; retain the established geography.')}</p><div class="sp-references">${refs.map(figure).join('')||'<p>No reference images recorded.</p>'}</div>${inspection.issues.length?`<ul class="sp-issues">${inspection.issues.map(i=>`<li class="${i.severity}"><b>${i.severity==='blocker'?'Needs attention':'Review'}</b> ${esc(i.message)}</li>`).join('')}</ul>`:'<p>Recorded references and handoffs checked.</p>'}<details><summary>Character states</summary><p>Use an approved state from this project, such as soaked, dry or a costume change.</p>${shot.characters.map(character=>{
      const selected=(shot.characterStates||[]).find(b=>b.character===character)?.stateId||'';
      const states=(ctx.snapshot.characterStates||[]).filter(v=>v.character===character&&v.approvalStatus==='approved'&&(!v.episode||v.episode===ctx.episode)&&(!v.scenes.length||v.scenes.includes(shot.scene)));
      return `<label>${esc(character)}<select data-character-state="${esc(character)}"><option value="">Base character identity</option>${states.map(v=>`<option value="${esc(v.id)}" ${v.id===selected?'selected':''}>${esc(v.name)}</option>`).join('')}</select></label>`;
    }).join('')}<button class="btn ghost" data-bind-states>Preview state change</button><button class="btn ghost" onclick="StudioProduction.library()">Manage project states</button></details><small>${esc(inspection.claim)}</small></div>`;
    if(shot.importedArchive)inspector.querySelector('details').hidden=true;
    if(!shot.importedArchive){
      const selected=shot.compositionReference;
      inspector.insertAdjacentHTML('beforeend',`<details class="sp-box" id="sp-reference-suggestions"><summary>Suggested camera and scene references</summary><p>Suggestions use approved openings from this scene and location. Character states remain explicit; no nearest-scene replacement is made.</p><label>Camera setup name<input id="sp-camera-setup" maxlength="100" value="${esc(shot.cameraSetupId||'')}" placeholder="For example: doorway reverse A"></label><p>${selected?`Selected ${esc(selected.shotId)} · ${esc(selected.role)}`:'No additional composition reference selected.'}</p><div class="sp-references">${inspection.suggestions.map((r,i)=>`<figure><img loading="lazy" src="${esc(url(r))}" alt="${esc(r.name)}"><figcaption><strong>${esc(r.name)}</strong><p>${esc(r.reason)}</p><small>Approved version ${esc(r.choice.candidateId.slice(0,12))}</small><button class="btn ghost" data-reference-choice="${i}">Preview this reference</button></figcaption></figure>`).join('')||'<p>No approved camera or scene match yet. Review an opening in this scene first; the project identity and location references remain visible above.</p>'}</div><button class="btn ghost" data-reference-choice="clear">${selected?'Preview removing extra reference':'Preview camera setup name'}</button></details>`);
      paintMediaReview(ctx,shot,inspection,inspector);
    }
  }
  function paintMediaReview(ctx,shot,inspection,root){
    const watch=shot.outcomes?.watch;
    if(!watch||!['candidate','approved'].includes(watch.status))return;
    const setting=ctx.snapshot.services.review,reports=inspection.mediaReviews||[],current=reports.slice().reverse().find(r=>r.current&&(!setting||r.binding.connectionId===setting.connectionId&&r.binding.model===setting.model&&r.binding.audioModel===setting.audioModel&&r.binding.videoFps===setting.videoFps));
    root.insertAdjacentHTML('beforeend',`<section class="sp-box sp-media-review"><h3>Review the actual footage</h3><p>Optional advice on the footage, incoming cut and audio. The report shows exactly what was examined. It uses this project’s review account and episode allowance. You still decide whether to approve WATCH.</p>${current?'':setting?`<p>${setting.videoFps?`Gemini video model: ${esc(setting.model)} · ${setting.videoFps} sampled frames/second`:`Visual model: ${esc(setting.model)} · audio model: ${esc(setting.audioModel)}`}</p><button class="btn ghost" data-media-review>Review footage & audio · ${cost(setting.estimateUsd)}</button>`:'<button class="btn ghost" data-services onclick="StudioProduction.services()">Connect optional media review</button>'}${reports.slice().reverse().map(r=>`<details ${r.id===current?.id?'open':''}><summary>${r.id===current?.id?'Current render review':r.current?'Additional review of this render':'Earlier version — report is out of date'}</summary><p>${esc(r.summary)}</p><small>${r.binding.provider==='gemini'?`Gemini video model: ${esc(r.binding.model)} · ${r.evidence.fps} sampled frames/second`:`Visual model: ${esc(r.binding.model)} · Audio model: ${esc(r.binding.audioModel)}`}</small><p>${esc(r.meaning)}</p>${r.findings.map((f,i)=>`<article class="sp-review-finding"><b>${f.seconds.toFixed(2)}s · ${esc(f.category)} · ${esc(f.confidence)} confidence</b><p>${esc(f.observation)}</p><p>${esc(f.suggestion)}</p>${r.current?`<button class="btn ghost" data-review-finding="${i}" data-report="${esc(r.id)}">Add to my direction</button>`:''}</article>`).join('')||'<p>No specific issue was reported in the examined evidence. Watch the full render before deciding.</p>'}<details><summary>Audio report</summary><p>${esc(r.audioReview)}</p></details><details><summary>Evidence examined</summary><p>${esc(r.evidence.scope)}</p>${r.cleanupPending?`<p>Temporary uploads still need cleanup.</p><button class="btn ghost" data-cleanup-review="${esc(r.jobId)}">Retry upload cleanup</button>`:''}<ul>${(r.evidence.videos||[]).map(v=>`<li><a href="${esc(url(v))}">${esc(v.label)}</a> · full ${v.duration.toFixed(2)}s · ${v.hasAudio?'with audio':'no audio stream'}</li>`).join('')}</ul><ul>${r.evidence.references.map(ref=>`<li><a href="${esc(url(ref))}">${esc(ref.label)}</a> · version ${esc((ref.candidateId||ref.version||ref.hash).slice(0,12))}</li>`).join('')}</ul>${r.evidence.omittedApprovedReferences?.length?`<p>Outside this sample: ${esc(r.evidence.omittedApprovedReferences.join(', '))}</p>`:''}<p>${r.evidence.audio.length} audio source(s); WATCH ${r.evidence.watchHasAudio?'contains an audio stream':'has no audio stream'}.</p><div class="sp-references">${r.evidence.frames.map(f=>`<figure><a href="${esc(url(f))}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(url(f))}" alt="${esc(f.label)}"></a><figcaption>${esc(f.label)}</figcaption></figure>`).join('')}</div><ul>${r.evidence.audio.map(a=>`<li><a href="${esc(url(a))}">${esc(a.label)}</a> · ${a.duration.toFixed(2)}s</li>`).join('')}</ul></details><ul>${r.limitations.map(l=>`<li>${esc(l)}</li>`).join('')}</ul></details>`).join('')}</section>`);
  }
  function paintTimeline(ctx){
    const root=ctx.root.querySelector('#sp-timeline'),timeline=ctx.snapshot.review.timeline;
    if(!root.querySelector('#sp-episode-player')){
      root.innerHTML=`<div class="sp-board-head"><div><h3>Watch the episode take shape</h3><p>Approved shots play in script order. Missing footage stays visible as a gap.</p></div></div><div class="sp-review-layout"><div><video id="sp-episode-player" class="sp-media" controls preload="metadata"></video><div id="sp-gap" class="sp-gap" hidden></div><p id="sp-play-position"></p><label>Episode position<input id="sp-scrub" type="range" min="0" step="0.1" value="0"></label><div class="sp-actions"><button class="btn ghost" data-timeline="previous">Previous shot</button><button class="btn" data-timeline="play">Play episode</button><button class="btn ghost" data-timeline="next">Next shot</button><button class="btn ghost" data-timeline="direct">Direct this shot</button></div><div id="sp-tracks" class="sp-tracks"></div></div><aside><h3>Review this moment</h3><label>Note<textarea id="sp-moment-note" placeholder="The pause needs another beat before the reverse."></textarea></label><button class="btn" data-timeline="note">Save timed note</button><div id="sp-trim"></div></aside></div><div id="sp-review-notes"></div><div id="sp-export"></div>`;
      const player=root.querySelector('video');
      player.onended=()=>{if(!ctx.snapshot.review.timeline.preview)playClip(ctx,(ctx.clipIndex||0)+1,true);};
      player.ontimeupdate=()=>{
        const clip=ctx.snapshot.review.timeline.clips[ctx.clipIndex||0];if(!clip)return;
        const master=ctx.snapshot.review.timeline.preview;
        ctx.playhead=master?player.currentTime:Math.max(clip.start,clip.start+player.currentTime-clip.in);
        if(master){const index=ctx.snapshot.review.timeline.clips.findIndex(c=>ctx.playhead>=c.start&&ctx.playhead<c.start+c.duration);if(index>=0&&index!==ctx.clipIndex){playClip(ctx,index,false,ctx.playhead-ctx.snapshot.review.timeline.clips[index].start);return;}}
        root.querySelector('#sp-play-position').textContent=`${clock(ctx.playhead)} / ${clock(ctx.snapshot.review.timeline.duration)} · ${clip.shotId}`;
        root.querySelector('#sp-scrub').value=ctx.playhead;
        if(!master&&!player.paused&&clip.out<clip.sourceDuration-.025&&player.currentTime>=clip.out-.025){player.pause();playClip(ctx,ctx.clipIndex+1,true);}
      };
      root.querySelector('#sp-scrub').oninput=e=>{
        const time=Number(e.target.value),clips=ctx.snapshot.review.timeline.clips;
        const index=clips.findIndex(c=>time>=c.start&&time<c.start+c.duration);
        if(index>=0)playClip(ctx,index,false,time-clips[index].start);
      };
    }
    root.querySelector('#sp-scrub').max=timeline.duration;
    window.StudioDrafts?.bind(root.querySelector('#sp-moment-note'),[ctx.project.id,ctx.episode,'timeline',timeline.fingerprint],{reset:true,revision:timeline.fingerprint});
    const playbackSignature=JSON.stringify([timeline.clips,timeline.preview?.files]);
    if(ctx.timelineSignature!==playbackSignature){
      ctx.timelineSignature=playbackSignature;
      root.querySelector('#sp-tracks').innerHTML=timeline.clips.map((c,i)=>`<button class="sp-clip ${c.gap?'gap':''}" data-clip="${i}" style="flex-grow:${Math.max(c.duration,1)}"><b>${esc(c.shotId)}</b><span>${clock(c.start)} · ${c.duration.toFixed(1)}s</span><small>${c.gap?'Missing approved footage':c.joinReview?'Review join':'Approved footage'}</small></button>`).join('')||'<p>No shots prepared yet.</p>';
      playClip(ctx,Math.min(ctx.clipIndex||0,Math.max(0,timeline.clips.length-1)),false);
    }
    const notesSignature=JSON.stringify(timeline.notes), notes=root.querySelector('#sp-review-notes');
    if(notes.dataset.signature!==notesSignature){notes.dataset.signature=notesSignature;notes.innerHTML=`<h3>Review notes</h3>${timeline.notes.map(n=>`<article class="sp-box"><b>${clock(n.seconds)} · ${esc(n.shotId)}</b><p>${esc(n.note)}</p><small>${n.resolved?'Addressed':n.fingerprint===timeline.fingerprint?'Current assembly':'Recorded against an earlier assembly'}</small><div class="sp-actions"><button class="btn ghost" data-note-shot="${esc(n.shotId)}">Open shot</button>${n.resolved?'':`<button class="btn ghost" data-resolve-note="${esc(n.id)}">Mark addressed</button>`}</div></article>`).join('')||'<p>No review notes yet.</p>'}`;}
    const exported=timeline.export?.fingerprint===timeline.fingerprint?timeline.export:null;
    const exportRoot=root.querySelector('#sp-export'),finishSignature=JSON.stringify([timeline.fingerprint,timeline.export,timeline.finishedCandidates,!!timeline.preview,ctx.snapshot.review.summary.reviewCurrent]);
    if(exportRoot.dataset.signature!==finishSignature){exportRoot.dataset.signature=finishSignature;exportRoot.innerHTML=`<div class="sp-box"><h3>${ctx.snapshot.review.summary.reviewCurrent?'Episode assembly approved':'Episode review'}</h3><p>${timeline.gaps?`${timeline.gaps} gaps need approved footage.`:timeline.preview?'Continuous preview ready. Watch timing, sound and joins before sign-off.':'Preparing continuous playback from approved clips. No provider spend.'}</p><div class="sp-actions"><button class="btn" data-timeline="approve" ${timeline.gaps||!timeline.preview?'disabled':''}>Approve episode assembly</button>${!timeline.preview&&!timeline.gaps?'<button class="btn ghost" data-timeline="assemble">Prepare continuous preview</button>':''}<button class="btn ghost" data-timeline="export" ${timeline.gaps?'disabled':''}>Create finishing handoff</button>${timeline.preview?`<a class="btn ghost" href="${esc(url(timeline.preview.files[0]))}" download>Download review movie</a>`:''}${exported?exported.files.map(f=>`<a class="btn ghost" href="${esc(url(f))}" download>${f.path.endsWith('.fcpxml')?'Download timeline':'Download sources & post brief'}</a>`).join(''):''}</div><small>Finishing handoff includes original approved media, shot direction, voice references and a project-specific post brief. It prepares files for editing; it does not launch Resolve or approve delivery.</small></div>`;
    if(exported)exportRoot.insertAdjacentHTML('beforeend',`<details class="sp-box"><summary>Return an edit from finishing</summary><p>Save the exported movie inside projects/${esc(ctx.project.id)}/media/. Import keeps it separate from source shots. Editor evidence is recorded, not independently certified.</p><form id="sp-finish-form" class="sp-form">${[['path','Studio movie path'],['hash','Movie SHA-256'],['resolveProjectId','Resolve project ID'],['resolveTimelineId','Resolve timeline ID'],['inspection','What was inspected and repaired? Include frame rate and inspected ranges.']].map(([name,label])=>`<label>${label}<input name="${name}" required maxlength="2000"></label>`).join('')}<label>Unresolved or uninspected work<textarea name="unresolved" maxlength="2000"></textarea></label><button class="btn" type="submit">Import returned edit</button></form></details>${(timeline.finishedCandidates||[]).map(c=>`<section class="sp-box"><h3>Returned edit · ${esc(c.status)}${c.current?'':' · earlier or unavailable version'}</h3>${c.current?`<video class="sp-media" controls preload="metadata" src="${esc(url(c.files[0]))}"></video>`:''}<p>Returned duration: ${clock(c.duration)} · source assembly: ${clock(c.sourceDuration)}. Review any timing differences.</p><p>${esc(c.evidence.inspection)}</p><p>${esc(c.unresolved||'No unresolved work declared by the editor.')}</p>${c.current&&c.status==='candidate'?`<button class="btn" data-finish="approve_finish" data-id="${esc(c.id)}">Approve returned edit</button><button class="btn ghost" data-finish="reject_finish" data-id="${esc(c.id)}">Reject returned edit</button>`:''}</section>`).join('')}`);
    const form=exportRoot.querySelector('#sp-finish-form');if(form)form.onsubmit=e=>{e.preventDefault();ctx.reviewSend(ctx,'register_finish',{...Object.fromEntries(new FormData(form)),timelineFingerprint:timeline.fingerprint,handoffId:timeline.handoffId});};
    exportRoot.onclick=e=>{const b=e.target.closest('[data-finish]');if(!b)return;const c=timeline.finishedCandidates.find(c=>c.id===b.dataset.id);ctx.reviewSend(ctx,b.dataset.finish,{candidateId:c.id,hash:c.files[0].hash,timelineFingerprint:timeline.fingerprint});};
    }

    if(ctx.mode==='review'&&ctx.snapshot.review.summary.assemblyReady&&!timeline.preview&&!ctx.busy&&!ctx.snapshot.jobs.some(j=>['queued','running','pending','unknown','interrupted'].includes(j.status))&&ctx.previewRequested!==timeline.fingerprint){ctx.previewRequested=timeline.fingerprint;queueMicrotask(()=>ctx.reviewSend(ctx,'assemble_cut',{timelineFingerprint:timeline.fingerprint}));}
  }
  function playClip(ctx,index,autoplay=false,offset=0){
    const clips=ctx.snapshot.review.timeline.clips,root=ctx.root.querySelector('#sp-timeline'),player=root.querySelector('video');
    if(index>=clips.length){player.pause();return;}
    index=Math.max(0,index);const clip=clips[index];if(!clip)return;
    ctx.clipIndex=index;ctx.playhead=clip.start+offset;
    const gap=root.querySelector('#sp-gap');gap.hidden=!clip.gap;player.hidden=clip.gap;
    if(clip.gap){player.pause();player.removeAttribute('src');player.load();gap.innerHTML=`<h3>${esc(clip.shotId)} · missing approved footage</h3><p>This gap stays in the episode until its render is approved.</p><button class="btn" data-timeline="direct">Open this shot</button>`;}
    else {
      const master=ctx.snapshot.review.timeline.preview;
      const source=url(master?master.files[0]:clip.file);
      const seek=()=>{player.currentTime=(master?clip.start:clip.in)+Math.min(offset,clip.duration-.01);if(autoplay)player.play().catch(()=>{});};
      if(player.getAttribute('src')!==source){player.src=source;player.onloadedmetadata=seek;}else seek();
    }
    root.querySelector('#sp-play-position').textContent=`${clock(ctx.playhead)} / ${clock(ctx.snapshot.review.timeline.duration)} · ${clip.shotId}`;
    root.querySelector('#sp-scrub').value=ctx.playhead;
    root.querySelector('#sp-trim').innerHTML=clip.gap?'':`<details><summary>Assembly timing · ${esc(clip.shotId)}</summary><p>Trims affect picture and its approved audio together. Original files are preserved.</p><label>In (seconds)<input id="sp-trim-in" type="number" min="0" step="0.01" value="${clip.in}"></label><label>Out (seconds)<input id="sp-trim-out" type="number" min="0" step="0.01" value="${clip.out}"></label><button class="btn ghost" data-timeline="trim">Save trim</button><button class="btn ghost" data-timeline="reset">Restore full clip</button></details>${index>0?'<button class="btn ghost" data-timeline="join">Mark incoming join reviewed</button>':''}`;
    for(const button of root.querySelectorAll('[data-clip]'))button.setAttribute('aria-current',Number(button.dataset.clip)===index?'true':'false');
  }
  function timelineClick(ctx,e){
    const root=ctx.root.querySelector('#sp-timeline'),action=e.target.closest('[data-timeline]')?.dataset.timeline;
    const selected=e.target.closest('[data-clip]');if(selected){playClip(ctx,Number(selected.dataset.clip));return;}
    const noteShot=e.target.closest('[data-note-shot]');if(noteShot){select(ctx,noteShot.dataset.noteShot);return;}
    const fingerprint=ctx.snapshot.review.timeline.fingerprint,clip=ctx.snapshot.review.timeline.clips[ctx.clipIndex||0];
    const resolve=e.target.closest('[data-resolve-note]');if(resolve){ctx.reviewSend(ctx,'resolve_note',{noteId:resolve.dataset.resolveNote,timelineFingerprint:fingerprint});return;}
    if(!action||!clip)return;
    const send=(command,extra={})=>ctx.reviewSend(ctx,command,{shotId:clip.shotId,timelineFingerprint:fingerprint,...extra});
    if(action==='previous'||action==='next')playClip(ctx,ctx.clipIndex+(action==='next'?1:-1));
    if(action==='play')playClip(ctx,ctx.clipIndex||0,true);
    if(action==='direct'){select(ctx,clip.shotId);const input=ctx.root.querySelector('#sp-direction');const note=root.querySelector('#sp-moment-note').value;if(note)input.value+=(input.value?'\n\n':'')+`At ${clock(ctx.playhead)} in the episode: ${note}`;window.StudioDrafts?.save(input);input.focus();}
    if(action==='note'){const input=root.querySelector('#sp-moment-note'),clearDraft=window.StudioDrafts?.capture(input);send('timeline_note',{note:input.value,seconds:ctx.playhead}).then(ok=>{if(ok)clearDraft?.();});}
    if(action==='join')send('review_join');
    if(action==='trim')send('trim_clip',{in:Number(root.querySelector('#sp-trim-in').value),out:Number(root.querySelector('#sp-trim-out').value)});
    if(action==='reset')send('reset_trim');
    if(action==='approve')send('review_cut');
    if(action==='export')send('export_cut');
    if(action==='assemble')send('assemble_cut');
  }
  function busy(ctx,value){
    const working=ctx.snapshot?.jobs?.some(j=>['queued','running','pending','unknown','interrupted'].includes(j.status));
    for(const button of ctx.root.querySelectorAll('[data-edit],[data-bind-states],[data-resolve-note],[data-reference-choice],[data-media-review]'))button.disabled=value||working||ctx.snapshot?.sourceChanged;
    for(const button of ctx.root.querySelectorAll('[data-timeline]')){
      const action=button.dataset.timeline;
      if(['play','previous','next','direct'].includes(action))continue;
      const timeline=ctx.snapshot?.review?.timeline;
      button.disabled=value||(['trim','reset','assemble','export'].includes(action)&&working)||(['approve','export'].includes(action)&&timeline?.gaps>0)||(action==='approve'&&!timeline?.preview);
    }
  }
  window.StudioReview={mount,paint,busy,show:mode=>show(active,mode),select:id=>select(active,id)};
})();
