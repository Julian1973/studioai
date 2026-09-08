/* Project production desk. Chat and controls both submit /api/project-command. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd = value => '$' + (Number(value || 0) / 1e6).toFixed(2);
  const roles = ['direction', 'keyframes', 'voices', 'animation'];
  let active = null;
  async function api(path, body) {
    const response = await fetch(BASE + path, body === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw Object.assign(new Error(result.error || 'The operation could not finish.'), {code:result.code});
    return result;
  }
  function stage(shot) {
    return ['see','hear','request','watch'].find(s => !(s === 'hear' && !shot.dialogue.length) && shot.outcomes?.[s]?.status !== 'approved') || 'done';
  }
  function modal(title) {
    document.getElementById('modal').classList.add('show');
    const sheet = document.getElementById('sheet');
    sheet.innerHTML = `<button class="x" onclick="document.getElementById('modal').classList.remove('show')" aria-label="Close">×</button><h2>${esc(title)}</h2><div id="workspace-dialog"></div>`;
    return sheet.querySelector('#workspace-dialog');
  }
  function showError(root, message) {
    let node = root.querySelector('[data-error]');
    if (!node) { node = document.createElement('p'); node.dataset.error = ''; node.setAttribute('role','alert'); root.append(node); }
    node.textContent = message;
  }
  async function importScript(file) {
    if(!file||!CURRENT_PROJECT)return;
    const projectId=CURRENT_PROJECT.id;
    const field=document.getElementById('projectPartScript');
    if(!field)return;
    field.setAttribute('aria-busy','true');
    try {
      if(file.size>15*1024*1024)throw new Error('Choose a script smaller than 15 MB.');
      const docData=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
      const {script}=await api('/api/project-script-extract',{projectId,docName:file.name,docData});
      if(!String(script||'').trim())throw new Error('No readable script text was found. Use a text-based document or paste the screenplay.');
      if(CURRENT_PROJECT?.id!==projectId||!field.isConnected)return;
      field.value=script;
      const title=document.getElementById('projectPartTitle');if(!title.value)title.value=file.name.replace(/\.[^.]+$/,'');
    } catch(error){if(field.isConnected)showError(field.parentElement,error.message);}
    finally{field.removeAttribute('aria-busy');}
  }
  async function connections() {
    const root = modal('Workspace connections');
    root.textContent = 'Loading connections…';
    try {
      const data = await api('/api/workspace/connections');
      if (!root.isConnected) return;
      root.innerHTML = `<p>Connect your own provider accounts. Keys are saved in your computer’s secure credential store. Each project chooses which connections to use.</p>
        <div class="sp-connections">${data.connections.map(c => `<article class="sp-box"><b>${esc(c.label)}</b><p>${esc(data.providers[c.provider].label)} · ${esc(c.maskedKey)} · ${esc(c.status)}</p><div class="sp-actions"><button class="btn ghost" data-check="${esc(c.id)}" ${c.enabled?'':'disabled'}>Check connection</button><button class="btn ghost" data-rotate="${esc(c.id)}">Replace key</button><button class="btn ghost" data-disable="${esc(c.id)}" ${c.enabled?'':'disabled'}>Disable</button></div></article>`).join('') || '<p>No connections yet. You can explore the studio without them.</p>'}</div>
        <form id="sp-connection-form" class="sp-form" autocomplete="off"><h3>Add connection</h3><input type="hidden" name="connectionId"><label>Provider<select name="provider">${Object.entries(data.providers).map(([id,p])=>`<option value="${esc(id)}">${esc(p.label)}</option>`).join('')}</select></label><label>Connection name<input name="label" placeholder="My production account" maxlength="100"></label><label>API key<input name="key" type="password" autocomplete="new-password" spellcheck="false" required></label><button class="btn" type="submit">Save securely</button><p data-error role="alert"></p></form>`;
      root.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        const form = event.currentTarget, button = form.querySelector('button');
        const body = {id:form.elements.connectionId.value || undefined, provider:form.elements.provider.value, label:form.elements.label.value, key:form.elements.key.value};
        form.elements.key.value = ''; button.disabled = true;
        try { await api('/api/workspace/connections', body); await connections(); }
        catch (error) { showError(root,error.message); button.disabled = false; }
        finally { body.key = ''; }
      };
      root.onclick = async event => {
        const button = event.target.closest('button'); if (!button) return;
        if (button.dataset.rotate) {
          const connection = data.connections.find(c => c.id === button.dataset.rotate), form = root.querySelector('form');
          form.elements.connectionId.value = connection.id; form.elements.provider.value = connection.provider;
          form.elements.label.value = connection.label; form.querySelector('h3').textContent = 'Replace connection key';
          form.elements.key.focus(); return;
        }
        const id = button.dataset.check || button.dataset.disable; if (!id) return;
        button.disabled = true;
        try { await api('/api/workspace/connections', {id,action:button.dataset.check?'check':'disable'}); await connections(); }
        catch (error) { showError(root,error.message); button.disabled = false; }
      };
    } catch (error) { showError(root,error.message); }
  }
  async function services(project = CURRENT_PROJECT) {
    if (!project) return;
    const root = modal(project.name + ' · Project services');
    root.textContent = 'Loading project services…';
    try {
      const [data, settings] = await Promise.all([api('/api/workspace/connections'),api('/api/project-services?projectId='+encodeURIComponent(project.id))]);
      if (!root.isConnected) return;
      root.innerHTML = `<p>These choices apply only to ${esc(project.name)}. Connect only the services needed for your next outcome.</p><button class="btn ghost" id="sp-manage-connections">Manage workspace connections</button>
        <form class="sp-form">${roles.map(role => {
          const setting = settings.services[role] || {}, options = data.connections.filter(c => c.enabled && data.providers[c.provider].roles.includes(role));
          return `<fieldset><legend>${esc(role[0].toUpperCase()+role.slice(1))}</legend><label>Account<select name="${role}-connection"><option value="">Connect later</option>${options.map(c=>`<option value="${esc(c.id)}" ${setting.connectionId===c.id?'selected':''}>${esc(c.label)} · ${esc(c.status)}</option>`).join('')}</select></label><label>Provider model ID<input name="${role}-model" value="${esc(setting.model||'')}" placeholder="${esc({direction:'Your OpenAI model ID',keyframes:'dola-seedream-5-0-pro-260628',voices:'eleven_v3',animation:'dreamina-seedance-2-5-260628'}[role])}"></label><label>Estimated maximum USD per request<input name="${role}-cost" type="number" min="0.000001" step="0.000001" value="${esc(setting.estimateUsd||'')}" placeholder="Check your provider pricing"></label>${role==='voices'?`<label>Voice casting — one Character name = Voice ID per line<textarea name="casting" placeholder="Hero = yourVoiceId">${esc(Object.entries(setting.casting||{}).map(([name,id])=>name+' = '+id).join('\n'))}</textarea></label>`:''}</fieldset>`;
        }).join('')}<p>Budget reservations use these estimates, including failed or uncertain work. They are studio spending controls, not a hard cap on your provider invoice. Animation currently uses the qualified 480p Seedance adapter.</p><button class="btn" type="submit">Save project services</button><p data-error role="alert"></p></form>`;
      root.querySelector('#sp-manage-connections').onclick = connections;
      root.querySelector('form').onsubmit = async event => {
        event.preventDefault(); const form = event.currentTarget, values = {};
        for (const role of roles) {
          values[role] = {connectionId:form.elements[role+'-connection'].value,model:form.elements[role+'-model'].value,estimateUsd:form.elements[role+'-cost'].value};
          if (role === 'voices') {
            values[role].casting = {};
            for (const line of form.elements.casting.value.split('\n').filter(line=>line.trim())) {
              const at = line.indexOf('=');
              if (at < 1) { showError(root,'Use Character name = Voice ID for each casting line.'); return; }
              values[role].casting[line.slice(0,at).trim()] = line.slice(at+1).trim();
            }
          }
        }
        const button = form.querySelector('button[type=submit]'); button.disabled = true;
        try { await api('/api/project-services',{projectId:project.id,services:values}); document.getElementById('modal').classList.remove('show'); if(active?.project.id===project.id)await refresh(active); }
        catch(error){showError(root,error.message);button.disabled=false;}
      };
    } catch(error){showError(root,error.message);}
  }
  async function library(project = CURRENT_PROJECT) {
    if(!project)return;
    const root=modal(project.name+' · Project library');root.textContent='Loading your library…';
    try {
      const {context}=await api('/api/project-library?projectId='+encodeURIComponent(project.id));
      if(!root.isConnected)return;
      root.innerHTML=`<p>Update the bible or add and revise references. Earlier source versions and original image files are retained. Production will identify which unfinished shots need refreshing.</p><form class="sp-form"><label>Library section<select name="group"><option value="bible">Show bible</option><option value="characters">Characters</option><option value="locations">Locations & scene plates</option><option value="props">Props</option></select></label><label id="sp-existing">Existing asset<select name="existing"></select></label><label id="sp-asset-name">Asset name<input name="name" maxlength="100"></label><label>Notes / bible<textarea name="notes" style="min-height:200px"></textarea></label><label id="sp-asset-image">New reference image (optional)<input name="image" type="file" accept="image/png,image/jpeg,image/webp"></label><button class="btn" type="submit">Save library revision</button><p data-error role="alert"></p></form>`;
      const form=root.querySelector('form');
      const entries=()=>form.elements.group.value==='characters'?Object.entries(context.assets.characters).map(([name,item])=>({name,...item})):context.assets[form.elements.group.value]||[];
      const selectAsset=()=>{const item=entries().find(a=>a.name===form.elements.existing.value);form.elements.name.value=item?.name||'';form.elements.notes.value=item?.notes||item?.key_features||'';form.elements.image.value='';};
      const chooseGroup=()=>{const bible=form.elements.group.value==='bible';for(const id of ['sp-existing','sp-asset-name','sp-asset-image'])root.querySelector('#'+id).hidden=bible;form.elements.existing.innerHTML='<option value="">Add an asset</option>'+entries().map(a=>`<option value="${esc(a.name)}">${esc(a.name)}</option>`).join('');selectAsset();if(bible)form.elements.notes.value=context.bible;};
      form.elements.group.onchange=chooseGroup;form.elements.existing.onchange=selectAsset;chooseGroup();
      form.onsubmit=async event=>{
        event.preventDefault();const button=form.querySelector('button');button.disabled=true;
        try {
          const file=form.elements.image.files[0];let imageData;
          if(file)imageData=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
          await api('/api/project-library',{projectId:project.id,sourceHash:context.sourceHash,group:form.elements.group.value,name:form.elements.name.value,notes:form.elements.notes.value,imageData});
          document.getElementById('modal').classList.remove('show');
          if(CURRENT_PROJECT?.id===project.id)await renderProjectWorkspace();
        } catch(error){showError(root,error.message);button.disabled=false;}
      };
    } catch(error){showError(root,error.message);}
  }
  async function mount(project, episodes) {
    if (active?.timer) clearTimeout(active.timer);
    const root = document.getElementById('projectProduction'); if(!root)return;
    let saved = {}; try { saved=JSON.parse(localStorage.getItem('studio.selection.'+project.id)||'{}'); } catch{}
    const episode = episodes.find(e=>String(e.number)===String(saved.episode)) || episodes[0];
    const ctx = active = {project,root,episode:episode?String(episode.number):null,shotId:saved.shotId||'',busy:false,timer:null,signature:''};
    root.innerHTML = `<div class="sp-heading"><div><span class="lab">Production agent</span><h2>You direct the film.</h2><p>Describe the change. Review the outcome. Keep moving.</p></div><button class="btn ghost" data-services>Project services</button></div>${episodes.length?`
      <label>Episode / sequence<select id="sp-episode">${episodes.map(e=>`<option value="${e.number}" ${String(e.number)===ctx.episode?'selected':''}>${e.number} · ${esc(e.title)}</option>`).join('')}</select></label>
      <div class="sp-budget"><p id="sp-budget-status"></p><form id="sp-budget-form"><label>Episode allowance (USD)<input type="number" min="0.01" step="0.01" id="sp-budget-amount" required></label><button class="btn ghost" type="submit">Approve allowance & prepare</button></form></div>
      <p id="sp-error" role="alert"></p><div id="sp-source-update"></div><div id="sp-jobs" aria-live="polite"></div><div class="sp-desk"><div class="sp-stage"><div id="sp-shot-list" class="sp-shot-list"></div><div id="sp-outcome"></div></div><aside class="sp-agent"><h3>Direct this shot</h3><div id="sp-scope"></div><div id="sp-feed" role="log" aria-live="polite"></div><form id="sp-chat"><label>Directing<select id="sp-direction-stage"><option value="see">Picture and staging</option><option value="hear">Voice performance</option><option value="watch">Animation and timing</option></select></label><label for="sp-direction">Your direction</label><textarea id="sp-direction" placeholder="Make the reaction more hesitant. Keep the voice and geography." required></textarea><button class="btn" type="submit">Send direction</button></form><p>Your agent uses this project’s bible, references and review notes. Approvals always come from you.</p></aside></div>`:'<p>Save your first script below. The production agent will prepare its shots after you connect direction and approve an episode allowance.</p>'}`;
    root.querySelector('[data-services]').onclick = ()=>services(project);
    if(!episode)return;
    root.querySelector('#sp-episode').onchange = event => {ctx.episode=event.target.value;ctx.shotId='';ctx.signature='';ctx.snapshot=null;refresh(ctx);};
    root.querySelector('#sp-budget-form').onsubmit = event=>{event.preventDefault();send(ctx,'budget',{amountUsd:root.querySelector('#sp-budget-amount').value});};
    root.querySelector('#sp-chat').onsubmit = async event => {
      event.preventDefault();const input=root.querySelector('#sp-direction'), message=input.value;
      if(await send(ctx,'chat',{message,stage:root.querySelector('#sp-direction-stage').value})&&input.value===message)input.value='';
    };
    root.querySelector('#sp-source-update').onclick=event=>{if(event.target.closest('[data-refresh-sources]'))send(ctx,'refresh_sources',{sourceHash:ctx.snapshot.sourceHash});};
    root.querySelector('#sp-shot-list').onclick = event=>{const button=event.target.closest('[data-shot]');if(button){ctx.shotId=button.dataset.shot;ctx.signature='';draw(ctx);}};
    root.querySelector('#sp-outcome').onclick = event=>{
      const button=event.target.closest('[data-command]');if(!button)return;
      const note=root.querySelector('#sp-review-note')?.value||'';
      send(ctx,button.dataset.command,{note});
    };
    root.querySelector('#sp-jobs').onclick=event=>{const button=event.target.closest('button');if(button?.dataset.resume)send(ctx,'resume',{jobId:button.dataset.resume});if(button?.dataset.reconcile)send(ctx,'reconcile',{jobId:button.dataset.reconcile,providerChecked:true,taskId:root.querySelector('#sp-recovery-task')?.value||undefined});};
    await refresh(ctx);
  }
  function current(ctx) {return active===ctx&&ctx.root.isConnected&&CURRENT_PROJECT?.id===ctx.project.id;}
  async function refresh(ctx) {
    if(!current(ctx)||!ctx.episode)return;
    const episode=ctx.episode;
    try {
      const snapshot=await api('/api/project-production?projectId='+encodeURIComponent(ctx.project.id)+'&episode='+encodeURIComponent(episode));
      if(!current(ctx)||ctx.episode!==episode)return;
      ctx.snapshot=snapshot;draw(ctx);
    } catch(error){if(current(ctx))ctx.root.querySelector('#sp-error').textContent=error.message;}
    clearTimeout(ctx.timer);
    if(current(ctx))ctx.timer=setTimeout(()=>{const job=ctx.snapshot?.jobs?.[0];if(!ctx.busy&&job?.status==='pending'&&job.taskId&&!job.code)send(ctx,'resume',{jobId:job.id});else refresh(ctx);},4000);
  }
  async function send(ctx, action, extra={}) {
    if(!current(ctx)||ctx.busy||!ctx.snapshot)return false;
    const shot=ctx.snapshot.state.shots.find(s=>s.id===ctx.shotId);
    const target=shot?.outcomes?.[stage(shot)];
    const episodeAtSend=ctx.episode, nextShot=shot&&stage(shot)==='watch'&&(action==='approve'||action==='chat'&&/^approve(?: watch)?[.!]?$/i.test(extra.message?.trim()||''))?ctx.snapshot.state.shots[ctx.snapshot.state.shots.indexOf(shot)+1]:null;
    const reviewId = action==='continue'&&shot&&stage(shot)==='watch'||action==='watch'||(action==='chat'&&/^(fire|render)$/i.test(extra.message?.trim()||'')) ? shot?.outcomes?.request?.id : target?.id;
    ctx.busy=true;ctx.root.querySelector('#sp-error').textContent='';setBusy(ctx,true);
    try {
      await api('/api/project-command',{projectId:ctx.project.id,episode:ctx.episode,shotId:ctx.shotId,
        action,commandId:crypto.randomUUID(),expectedRevision:ctx.snapshot.state.revision,reviewId,...extra});
      if(nextShot&&current(ctx)&&ctx.episode===episodeAtSend){ctx.shotId=nextShot.id;ctx.signature='';}
      await refresh(ctx);return true;
    } catch(error){
      if(current(ctx)){await refresh(ctx);ctx.root.querySelector('#sp-error').textContent=error.message;}return false;
    } finally {ctx.busy=false;if(current(ctx))setBusy(ctx,false);}
  }
  function setBusy(ctx,busy){const working=['queued','running','pending','unknown'].includes(ctx.snapshot?.jobs?.[0]?.status);ctx.root.querySelectorAll('button[type=submit],[data-command]').forEach(button=>{button.disabled=busy||((working||ctx.snapshot?.sourceChanged)&&!button.closest('#sp-budget-form'));button.title=ctx.snapshot?.sourceChanged?'Review the updated project sources first':working?'Preparing or recovering the current outcome':'';});}
  function draw(ctx) {
    const {state,jobs}=ctx.snapshot,root=ctx.root;
    let shot=state.shots.find(s=>s.id===ctx.shotId);
    if(!shot){shot=state.shots.find(s=>stage(s)!=='done')||state.shots[0];ctx.shotId=shot?.id||'';}
    try{localStorage.setItem('studio.selection.'+ctx.project.id,JSON.stringify({episode:ctx.episode,shotId:ctx.shotId}));}catch{}
    root.querySelector('#sp-source-update').innerHTML=ctx.snapshot.sourceChanged?'<div class="sp-box"><h3>Project sources changed</h3><p>Review the updated bible and references in your library. Apply them to unfinished pictures while preserving finished shots and approved voices. A changed screenplay needs its own new episode or sequence version.</p><button class="btn ghost" data-refresh-sources>Use updated project sources</button></div>':'';
    const budget=state.budget;
    root.querySelector('#sp-budget-status').textContent=`Allowance ${usd(budget.allowance)} · committed estimates ${usd(budget.committed)} · in progress ${usd(budget.reserved)} · remaining ${usd(budget.allowance-budget.committed-budget.reserved)}`;
    const last=jobs[0]?.status!=='completed'?jobs[0]:null;
    root.querySelector('#sp-jobs').innerHTML=last?`<div class="sp-box"><b>${esc(last.kind.toUpperCase())} · ${esc(last.status)}</b><p>${esc(last.message||'Working on your outcome…')}</p>${last.taskId?`<small>Provider task ${esc(last.taskId)}</small>`:''}${['pending','interrupted'].includes(last.status)?`<button class="btn ghost" data-resume="${esc(last.id)}">Resume job</button>`:''}${last.status==='unknown'?`<details><summary>Recover an uncertain request</summary><p>Check your provider account first. If a render task exists, enter its ID to resume it. Otherwise close this request; its estimate stays counted.</p>${last.kind==='watch'?'<label>Provider task ID (optional)<input id="sp-recovery-task"></label>':''}<button class="btn ghost" data-reconcile="${esc(last.id)}">I checked the provider — reconcile this request</button></details>`:''}</div>`:'';
    root.querySelector('#sp-shot-list').innerHTML=state.shots.map(s=>`<button class="btn ${s.id===ctx.shotId?'':'ghost'}" data-shot="${esc(s.id)}" aria-pressed="${s.id===ctx.shotId}">Scene ${s.scene} · ${esc(s.id)}<small>${esc(stage(s)==='done'?'Approved':stage(s).toUpperCase())}</small></button>`).join('');
    root.querySelector('#sp-scope').textContent=shot?`Scene ${shot.scene} · ${shot.id} · ${shot.title}`:'Episode preparation';
    const feed=root.querySelector('#sp-feed'),messages=state.messages.filter(m=>!m.shotId||m.shotId===ctx.shotId);
    const feedSignature=JSON.stringify(messages);
    if(feed.dataset.signature!==feedSignature){feed.innerHTML=messages.map(m=>`<div class="sp-message ${m.role==='user'?'sp-user':''}"><b>${m.role==='user'?'You':'Production agent'}</b><p>${esc(m.text)}</p></div>`).join('')||'<p>Ready when you are. Set your services and episode allowance to begin.</p>';feed.dataset.signature=feedSignature;feed.scrollTop=feed.scrollHeight;}
    const signature=JSON.stringify(shot||state.shots);
    if(ctx.signature===signature){setBusy(ctx,ctx.busy);return;}
    ctx.signature=signature;
    const outcome=root.querySelector('#sp-outcome');
    if(!shot){outcome.innerHTML='<div class="sp-box"><h3>Your script becomes directed shots</h3><p>The director prepares emotional beats, camera coverage, performance and matched generation prompts. Your first review is the SEE keyframe.</p><button class="btn" data-command="prepare">Prepare my episode</button></div>';return;}
    const s=stage(shot), candidate=shot.outcomes?.[s];
    if(!root.querySelector('#sp-direction').value)root.querySelector('#sp-direction-stage').value=s==='hear'?'hear':['request','watch','done'].includes(s)?'watch':'see';
    const media=(item,kind)=>{
      if(!item?.files?.length)return '';
      const url=BASE+'/'+item.files[0].path.split('/').map(encodeURIComponent).join('/');
      return kind==='see'?`<img class="sp-media" src="${esc(url)}" alt="${esc(shot.id)} opening keyframe">`:kind==='hear'?`<audio class="sp-media" controls preload="metadata" src="${esc(url)}"></audio>`:`<video class="sp-media" controls preload="metadata" src="${esc(url)}"></video>`;
    };
    outcome.innerHTML=`<h3>${esc(shot.title)}</h3><p>${esc(shot.emotion)}</p>${shot.continuityReview?`<p class="sp-notice">${esc(shot.continuityReview)}</p>`:''}<div class="sp-step-labels">${['see','hear','request','watch'].map(k=>`<span class="${s===k?'current':''}">${k==='request'?'Render request':k.toUpperCase()} · ${esc(shot.outcomes?.[k]?.status||(k==='hear'&&!shot.dialogue.length?'No dialogue':'Next'))}</span>`).join('')}</div>
      ${['see','hear','watch'].filter(k=>shot.outcomes?.[k]).map(k=>`<details class="sp-box" ${(k===s||s==='done'&&k==='watch')?'open':''}><summary>${k.toUpperCase()} · ${esc(shot.outcomes[k].status)}</summary>${k==='see'&&(shot.outcomes[k].references||[]).find(r=>r.name.startsWith('Previous approved ending'))?`<figure><figcaption>Incoming approved ending · continuity reference</figcaption><img class="sp-media" src="${esc(BASE+'/'+shot.outcomes[k].references.find(r=>r.name.startsWith('Previous approved ending')).path)}" alt="Previous approved ending"></figure>`:''}${media(shot.outcomes[k],k)}${shot.outcomes[k].audioAuthority?`<p>${esc(shot.outcomes[k].audioAuthority.note)}</p>`:''}</details>`).join('')}
      ${shot.outcomes?.request?`<details class="sp-box" ${s==='request'?'open':''}><summary>WATCH request · ${shot.outcomes.request.duration}s · ${esc(shot.outcomes.request.resolution)} · $${Number(shot.outcomes.request.binding.estimateUsd).toFixed(2)} estimated</summary><p>Model: ${esc(shot.outcomes.request.binding.model)}</p><h4>Prompt</h4><pre>${esc(shot.outcomes.request.prompt)}</pre><h4>Script</h4><pre>${esc(shot.outcomes.request.source)}</pre><button class="btn ghost" data-command="request">Refresh request for review</button><h4>References</h4><div class="sp-references">${shot.outcomes.request.images.map(r=>`<figure><img src="${esc(BASE+'/'+r.path)}" alt="${esc(r.name)}"><figcaption>${esc(r.name)}</figcaption></figure>`).join('')}</div></details>`:''}
      <div class="sp-actions">${s==='done'?'<p>Render approved. Select the next shot.</p>':candidate?.status==='candidate'?`<button class="btn" data-command="approve">${s==='request'?'Approve request & render':'Approve '+s.toUpperCase()+' & continue'}</button><button class="btn ghost" data-command="reject">Reject ${s==='request'?'request':s.toUpperCase()}</button>`:`<button class="btn" data-command="${s==='watch'?'watch':'continue'}">${s==='watch'?'Render approved request':'Prepare '+(s==='request'?'WATCH request':s.toUpperCase())}</button>`}</div>
      ${s!=='done'?'<label>Review note (optional)<textarea id="sp-review-note" placeholder="What should improve?"></textarea></label>':''}
      <details class="sp-box"><summary>Direction, source and shot history</summary><p><b>Acting:</b> ${esc(shot.performance)}</p><p><b>Camera:</b> ${esc(shot.camera)}</p><p><b>Geography:</b> ${esc(shot.geography)}</p><p><b>Handoff:</b> ${esc(shot.transition)}</p><h4>SEE prompt</h4><pre>${esc(shot.seePrompt)}</pre><h4>WATCH prompt</h4><pre>${esc(shot.watchPrompt)}</pre><h4>Exact dialogue</h4><pre>${esc(shot.dialogue.map(d=>d.speaker+': '+d.text).join('\n'))}</pre><p>${shot.versions?.length||0} previous outcome versions retained.</p>${(shot.versions||[]).map(v=>`<details><summary>${esc(v.stage.toUpperCase())} · ${esc(v.status)}</summary>${media(v,v.stage)}</details>`).join('')}</details>`;
    setBusy(ctx,ctx.busy);
  }
  window.StudioProduction={mount,connections,services,library,importScript};
})();
