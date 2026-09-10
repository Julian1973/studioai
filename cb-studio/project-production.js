/* Project production desk. Chat and controls both submit /api/project-command. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd = value => '$' + (Number(value || 0) / 1e6).toFixed(2);
  const roles = ['direction', 'keyframes', 'voices', 'animation', 'review'];
  let active = null;
  async function api(path, body) {
    const response = await fetch(BASE + path, body === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw Object.assign(new Error(result.error || 'The operation could not finish.'), {code:result.code});
    return result;
  }
  function stage(shot) {
    if(shot?.importedArchive)return 'archive';
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
      window.StudioDrafts?.save(field);window.StudioDrafts?.save(title);
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
          return `<fieldset><legend>${esc(role[0].toUpperCase()+role.slice(1))}</legend><label>Account<select name="${role}-connection"><option value="">Connect later</option>${options.map(c=>`<option value="${esc(c.id)}" ${setting.connectionId===c.id?'selected':''}>${esc(c.label)} · ${esc(c.status)}</option>`).join('')}</select></label><label>Provider model ID<input name="${role}-model" value="${esc(setting.model||(role==='direction'?'gpt-6-astra':''))}" placeholder="${esc({direction:'Your OpenAI model ID',keyframes:'dola-seedream-5-0-pro-260628',voices:'eleven_v3',animation:'dreamina-seedance-2-5-260628',review:'Your vision model with structured output'}[role])}"></label><label>Estimated maximum USD per request<input name="${role}-cost" type="number" min="0.000001" step="0.000001" value="${esc(setting.estimateUsd||(role==='direction'?2:''))}" placeholder="Check your provider pricing"></label>${['keyframes','voices','animation'].includes(role)?`<label>Optional account rate · USD per ${role==='voices'?'1,000 characters':role==='animation'?'video second':'image'}<input type="number" min="0.000001" step="0.000001" name="${role}-unit" value="${esc(setting.unitUsd??'')}" placeholder="Your provider rate"></label>`:''}${role==='direction'?`<details><summary>Automatic model routing</summary><p>Story and performance stay with the creative director. Only exact prompt-maintenance requests use the routine model. Workflow explanations use the assistant. Approvals and navigation do not call AI.</p><label><input type="checkbox" name="direction-routing" ${setting.routing||!setting.model?'checked':''} style="width:auto"> Route by task</label>${[['creative','Story and creative direction','gpt-6-astra',2],['routine','Prompt wording only','gpt-5.6-terra',.5],['assistant','Workflow explanations','gpt-5.6-luna',.1]].map(([task,label,model,cost])=>`<label>${label}<input name="route-${task}-model" value="${esc(setting.routing?.[task]?.model||model)}"></label><label>Estimated maximum USD per request<input type="number" min="0.000001" step="0.000001" name="route-${task}-cost" value="${esc(setting.routing?.[task]?.estimateUsd??cost)}"></label>`).join('')}<p>Uses the direction account above. Model access must be available on that account. A failed call never automatically triggers another paid call.</p></details>`:''}${role==='review'?`<label data-review-audio>Audio-input model ID<input name="review-audio-model" value="${esc(setting.audioModel||'')}" placeholder="Your audio-input Chat Completions model"></label><label data-review-video hidden>Video inspection<select name="review-fps">${[[4,"Detailed motion review"],[1,"Overview"],[8,"Closer motion inspection"]].map(([n,label])=>`<option value="${n}" ${Number(setting.videoFps||4)===n?"selected":""}>${label}</option>`).join("")}</select></label><p data-review-description></p>`:''}${role==='voices'?`<label>Voice casting — one Character name = Voice ID per line<textarea name="casting" placeholder="Hero = yourVoiceId">${esc(Object.entries(setting.casting||{}).map(([name,id])=>name+' = '+id).join('\n'))}</textarea></label>`:''}</fieldset>`;
        }).join('')}<p>HEAR reserves the voice estimate for each dialogue line. Budget reservations use these estimates, including failed or uncertain work. They are studio spending controls, not a hard cap on your provider invoice. Animation currently uses the qualified 480p Seedance adapter.</p><button class="btn" type="submit">Save project services</button><p data-error role="alert"></p></form>`;
      root.querySelector('#sp-manage-connections').onclick = connections;
      const serviceForm=root.querySelector('form');
      const updateReview=()=>{
        const google=data.connections.find(c=>c.id===serviceForm.elements['review-connection'].value)?.provider==='gemini';
        root.querySelector('[data-review-audio]').hidden=google;
        serviceForm.elements['review-audio-model'].disabled=google;
        root.querySelector('[data-review-video]').hidden=!google;
        root.querySelector('[data-review-description]').textContent=google?'Reviews the complete shot video with audio, the preceding approved shot, and approved references. Detailed review samples 4 frames per second; brief faults can still be missed. The estimate must cover the entire review. You approve WATCH.':'Optional review of sampled frames and separately extracted audio. The estimate must cover both model calls. You approve WATCH.';
        serviceForm.elements['review-model'].placeholder=google?'Your Gemini video model ID':'Your vision model with structured output';
      };
      serviceForm.elements['review-connection'].onchange=updateReview;updateReview();
      root.querySelector('form').onsubmit = async event => {
        event.preventDefault(); const form = event.currentTarget, values = {};
        for (const role of roles) {
          values[role] = {connectionId:form.elements[role+'-connection'].value,model:form.elements[role+'-model'].value,estimateUsd:form.elements[role+'-cost'].value};
          if (['keyframes','voices','animation'].includes(role)) values[role].unitUsd=form.elements[role+'-unit'].value;
          if (role === 'direction' && form.elements['direction-routing'].checked) values[role].routing=Object.fromEntries(['creative','routine','assistant'].map(task=>[task,{model:form.elements['route-'+task+'-model'].value,estimateUsd:form.elements['route-'+task+'-cost'].value}]));
          if (role === 'review') {values[role].audioModel=form.elements['review-audio-model'].value;values[role].videoFps=form.elements['review-fps'].value;}
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
      root.insertAdjacentHTML('afterbegin','<button class="btn ghost" data-manage-states>Character states</button>');
      root.querySelector('[data-manage-states]').onclick=()=>states(project);
      form.querySelector('button[type=submit]').insertAdjacentHTML('beforebegin','<label id="sp-traits">Identity traits — one trait = value per line<textarea name="traits" placeholder="species = bear\ncolour = lavender\nwings = none"></textarea></label><label id="sp-approve-asset"><input type="checkbox" name="approve" style="width:auto"> I approve this reference and its identity information</label>');
      const entries=()=>form.elements.group.value==='characters'?Object.entries(context.assets.characters).map(([name,item])=>({name,...item})):context.assets[form.elements.group.value]||[];
      const selectAsset=()=>{const item=entries().find(a=>a.name===form.elements.existing.value);form.elements.name.value=item?.name||'';form.elements.notes.value=item?.notes||item?.key_features||'';form.elements.image.value='';form.elements.traits.value=Object.entries(item?.identityTraits||{}).map(([k,v])=>k+' = '+v).join('\n');form.elements.approve.checked=false;};
      const chooseGroup=()=>{const bible=form.elements.group.value==='bible';for(const id of ['sp-existing','sp-asset-name','sp-asset-image','sp-approve-asset'])root.querySelector('#'+id).hidden=bible;root.querySelector('#sp-traits').hidden=form.elements.group.value!=='characters';form.elements.existing.innerHTML='<option value="">Add an asset</option>'+entries().map(a=>`<option value="${esc(a.name)}">${esc(a.name)}</option>`).join('');selectAsset();if(bible)form.elements.notes.value=context.bible;};
      const draftLibrary=()=>window.StudioDrafts?.form(form,[project.id,'library',form.elements.group.value,form.elements.existing.value],['name','notes','traits'],context.sourceHash);
      form.elements.group.onchange=()=>{chooseGroup();draftLibrary();};form.elements.existing.onchange=()=>{selectAsset();draftLibrary();};chooseGroup();draftLibrary();
      form.onsubmit=async event=>{
        event.preventDefault();const button=form.querySelector('button');button.disabled=true;
        try {
          const file=form.elements.image.files[0];let imageData;
          if(file)imageData=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
          const identityTraits=Object.fromEntries(form.elements.traits.value.split('\n').filter(s=>s.trim()).map(line=>{const at=line.indexOf('=');if(at<1)throw new Error('Use trait = value on each identity line.');return [line.slice(0,at).trim(),line.slice(at+1).trim()];}));
          await api('/api/project-library',{projectId:project.id,sourceHash:context.sourceHash,group:form.elements.group.value,name:form.elements.name.value,notes:form.elements.notes.value,imageData,approve:form.elements.approve.checked,...(form.elements.group.value==='characters'?{identityTraits}:{})});
          for(const name of ['name','notes','traits'])window.StudioDrafts?.clear(form.elements[name]);
          document.getElementById('modal').classList.remove('show');
          if(CURRENT_PROJECT?.id===project.id)await renderProjectWorkspace();
        } catch(error){showError(root,error.message);button.disabled=false;}
      };
    } catch(error){showError(root,error.message);}
  }
  async function states(project = CURRENT_PROJECT) {
    const root=modal(project.name+' · Character states');root.textContent='Loading project states…';
    try {
      const {context}=await api('/api/project-library?projectId='+encodeURIComponent(project.id));
      if(!root.isConnected)return;
      root.innerHTML=`<p>Keep character identity fixed while approving changes such as costume, wetness or damage. Each state has its own image and scope.</p><form class="sp-form"><label>State<select name="existing"><option value="">Add a character state</option>${context.characterStates.map(s=>`<option value="${esc(s.id)}">${esc(s.character)} · ${esc(s.name)} · ${esc(s.approvalStatus)}</option>`).join('')}</select></label><label>Character<select name="character">${Object.keys(context.assets.characters).map(c=>`<option>${esc(c)}</option>`).join('')}</select></label><label>State name<input name="name" placeholder="Soaked after the storm" required></label><label>What changes, and what stays consistent<textarea name="notes"></textarea></label><label>Episode scope<select name="episode"><option value="">All episodes</option>${context.episodes.map(e=>`<option value="${e.number}">${e.number} · ${esc(e.title)}</option>`).join('')}</select></label><label>Scene numbers (optional, comma separated)<input name="scenes" placeholder="2, 3"></label><img id="sp-state-image" class="sp-media" hidden alt="Character state reference"><label>Reference image<input name="image" type="file" accept="image/png,image/jpeg,image/webp"></label><label><input name="approve" type="checkbox" style="width:auto"> I approve this state for its selected scenes</label><button class="btn" type="submit">Save character state</button><p data-error role="alert"></p></form>`;
      const form=root.querySelector('form'),preview=root.querySelector('#sp-state-image');let imageData;
      form.elements.existing.onchange=()=>{const s=context.characterStates.find(s=>s.id===form.elements.existing.value);form.elements.character.value=s?.character||Object.keys(context.assets.characters)[0]||'';form.elements.name.value=s?.name||'';form.elements.notes.value=s?.notes||'';form.elements.episode.value=s?.episode||'';form.elements.scenes.value=s?.scenes.join(', ')||'';form.elements.approve.checked=false;form.elements.image.value='';imageData=undefined;preview.hidden=!s?.image;if(s?.image)preview.src=BASE+'/'+s.image;};
      const draftState=()=>window.StudioDrafts?.form(form,[project.id,'state',form.elements.existing.value],['character','name','notes','episode','scenes'],context.sourceHash);
      const chooseState=form.elements.existing.onchange;form.elements.existing.onchange=()=>{chooseState();draftState();};draftState();
      form.elements.image.onchange=async()=>{const file=form.elements.image.files[0];if(!file)return;imageData=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});preview.src=imageData;preview.hidden=false;};
      form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;try{await api('/api/project-library',{projectId:project.id,sourceHash:context.sourceHash,group:'states',id:form.elements.existing.value||undefined,character:form.elements.character.value,name:form.elements.name.value,notes:form.elements.notes.value,episode:form.elements.episode.value,scenes:form.elements.scenes.value.split(',').map(s=>s.trim()).filter(Boolean).map(Number),imageData,approve:form.elements.approve.checked});for(const name of ['character','name','notes','episode','scenes'])window.StudioDrafts?.clear(form.elements[name]);document.getElementById('modal').classList.remove('show');if(CURRENT_PROJECT?.id===project.id)await renderProjectWorkspace();}catch(error){showError(root,error.message);button.disabled=false;}};
    } catch(error){showError(root,error.message);}
  }
  async function mount(project, episodes) {
    if (active?.timer) clearTimeout(active.timer);
    const root = document.getElementById('projectProduction'); if(!root)return;
    let saved = {}; try { saved=JSON.parse(localStorage.getItem('studio.selection.'+project.id)||'{}'); } catch{}
    const episode = episodes.find(e=>String(e.number)===String(saved.episode)) || episodes[0];
    const ctx = active = {project,root,episode:episode?String(episode.number):null,shotId:saved.shotId||'',busy:false,timer:null,signature:''};
    root.innerHTML = `<div class="sp-heading"><div><span class="lab">Production agent</span><h2>Direct your episode.</h2></div><button class="btn ghost" data-services>Project services</button></div>${episodes.length?`
      <label>Episode / sequence<select id="sp-episode">${episodes.map(e=>`<option value="${e.number}" ${String(e.number)===ctx.episode?'selected':''}>${e.number} · ${esc(e.title)}</option>`).join('')}</select></label>
      <div id="sp-readiness"></div><div class="sp-budget"><p id="sp-budget-status"></p><details id="sp-budget-edit" open><summary>Episode allowance</summary><form id="sp-budget-form"><label>Episode allowance (USD)<input type="number" min="0.01" step="0.01" id="sp-budget-amount" required></label><button class="btn ghost" type="submit">Approve allowance & prepare</button></form></details></div>
      <p id="sp-error" role="alert"></p><div id="sp-source-update"></div><div id="sp-jobs" aria-live="polite"></div><div class="sp-desk"><div class="sp-stage"><div id="sp-shot-list" class="sp-shot-list"></div><div id="sp-outcome"></div></div><aside class="sp-agent"><h3>Direct this shot</h3><div id="sp-scope"></div><div id="sp-feed" role="log" aria-live="polite"></div><form id="sp-chat"><label>Directing<select id="sp-direction-stage"><option value="see">Picture and staging</option><option value="hear">Voice performance</option><option value="watch">Animation and timing</option></select></label><label for="sp-direction">Your direction</label><textarea id="sp-direction" placeholder="Make the reaction more hesitant. Keep the voice and geography." required></textarea><button class="btn" type="submit">Send direction</button></form><p>Your agent uses this project’s bible, references and review notes. Approvals always come from you.</p></aside></div>`:'<p>Save your first script below. The production agent will prepare its shots after you connect direction and approve an episode allowance.</p>'}`;
    root.querySelector('[data-services]').onclick = ()=>services(project);
    if(!episode)return;
    root.querySelector('#sp-episode').onchange = event => {ctx.episode=event.target.value;ctx.shotId='';ctx.signature='';ctx.snapshot=null;refresh(ctx);};
    root.querySelector('#sp-budget-form').onsubmit = event=>{event.preventDefault();send(ctx,'budget',{amountUsd:root.querySelector('#sp-budget-amount').value});};
    root.querySelector('#sp-chat').onsubmit = async event => {
      event.preventDefault();const input=root.querySelector('#sp-direction'), message=input.value;
      const clearDraft=window.StudioDrafts?.capture(input);
      if(await send(ctx,'chat',{message,stage:root.querySelector('#sp-direction-stage').value}))clearDraft?.();
    };
    root.querySelector('#sp-direction-stage').onchange=()=>{ctx.directionManual=true;window.StudioDrafts?.save(root.querySelector('#sp-direction'));};
    root.querySelector('#sp-source-update').onclick=event=>{if(event.target.closest('[data-refresh-sources]'))send(ctx,'refresh_sources',{sourceHash:ctx.snapshot.sourceHash});};
    root.querySelector('#sp-shot-list').onclick = event=>{const button=event.target.closest('[data-shot]');if(button){ctx.shotId=button.dataset.shot;ctx.signature='';draw(ctx);}};
    root.querySelector('#sp-outcome').onclick = event=>{
      const button=event.target.closest('[data-command]');if(!button)return;
      const note=root.querySelector('#sp-review-note')?.value||'';
      const clearDraft=window.StudioDrafts?.capture(root.querySelector('#sp-review-note'));
      send(ctx,button.dataset.command,{note}).then(ok=>{if(ok&&['approve','reject'].includes(button.dataset.command))clearDraft?.();});
    };
    root.querySelector('#sp-jobs').onclick=event=>{const button=event.target.closest('button');if(button?.dataset.cleanup)send(ctx,'cleanup_review_uploads',{jobId:button.dataset.cleanup});if(button?.dataset.resume)send(ctx,'resume',{jobId:button.dataset.resume});if(button?.dataset.reconcile)send(ctx,'reconcile',{jobId:button.dataset.reconcile,providerChecked:true,taskId:root.querySelector('#sp-recovery-task')?.value||undefined});};
    root.querySelector('#sp-outcome').insertAdjacentHTML('afterend','<div id="sp-learning"></div>');
    root.querySelector('#sp-learning').onclick=e=>{const b=e.target.closest('[data-retire-learning]');if(b)send(ctx,'retire_learning',{learningId:b.dataset.retireLearning});};
    root.querySelector('#sp-learning').onsubmit=e=>{e.preventDefault();const form=e.target,stage=form.elements.stage.value,shot=ctx.snapshot.state.shots.find(s=>s.id===ctx.shotId);send(ctx,'save_learning',{stage,candidateId:shot?.outcomes?.[stage]?.id,note:form.elements.note.value});};
    window.StudioReview?.mount(ctx,send,draw);
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
    const episodeAtSend=ctx.episode, nextShot=shot&&stage(shot)==='watch'&&(action==='approve'||action==='chat'&&/^approve(?: watch| and continue)?[.!]?$/i.test(extra.message?.trim()||''))?ctx.snapshot.state.shots[ctx.snapshot.state.shots.indexOf(shot)+1]:null;
    const mediaReview=action==='media_review'||action==='chat'&&/^review (footage|render)[.!]?$/i.test(extra.message?.trim()||'');
    const reviewId = mediaReview?shot?.outcomes?.watch?.id:action==='continue'&&shot&&stage(shot)==='watch'||action==='watch'||(action==='chat'&&/^(fire|render)$/i.test(extra.message?.trim()||'')) ? shot?.outcomes?.request?.id : target?.id;
    ctx.busy=true;ctx.root.querySelector('#sp-error').textContent='';setBusy(ctx,true);
    if(action==='approve'||(action==='chat'&&/^approve(?: (?:see|hear|watch|request))?[.!]?$/i.test(extra.message?.trim()||'')))ctx.directionManual=false;
    try {
      await api('/api/project-command',{projectId:ctx.project.id,episode:ctx.episode,shotId:ctx.shotId,
        action,commandId:crypto.randomUUID(),expectedRevision:ctx.snapshot.state.revision,reviewId,proposalId:shot?.proposal?.id,...extra});
      if(nextShot&&current(ctx)&&ctx.episode===episodeAtSend){ctx.shotId=nextShot.id;ctx.signature='';}
      await refresh(ctx);return true;
    } catch(error){
      if(current(ctx)){await refresh(ctx);ctx.root.querySelector('#sp-error').textContent=error.message;}return false;
    } finally {ctx.busy=false;if(current(ctx))setBusy(ctx,false);}
  }
  function setBusy(ctx,busy){const working=['queued','running','pending','unknown'].includes(ctx.snapshot?.jobs?.[0]?.status);ctx.root.querySelectorAll('button[type=submit],[data-command]').forEach(button=>{button.disabled=busy||((working||ctx.snapshot?.sourceChanged)&&!button.closest('#sp-budget-form'));button.title=ctx.snapshot?.sourceChanged?'Review the updated project sources first':working?'Preparing or recovering the current outcome':'';});window.StudioReview?.busy(ctx,busy);}
  function draw(ctx) {
    const {state,jobs}=ctx.snapshot,root=ctx.root;
    let shot=state.shots.find(s=>s.id===ctx.shotId);
    if(!shot){shot=state.shots.find(s=>stage(s)!=='done')||state.shots[0];ctx.shotId=shot?.id||'';}
    try{localStorage.setItem('studio.selection.'+ctx.project.id,JSON.stringify({episode:ctx.episode,shotId:ctx.shotId}));}catch{}
    root.querySelector('#sp-source-update').innerHTML=ctx.snapshot.sourceChanged?'<div class="sp-box"><h3>Project sources changed</h3><p>Review the updated bible and references in your library. Apply them to unfinished pictures while preserving finished shots and approved voices. A changed screenplay needs its own new episode or sequence version.</p><button class="btn ghost" data-refresh-sources>Use updated project sources</button></div>':'';
    const readiness=ctx.snapshot.readiness;
    root.querySelector('#sp-readiness').innerHTML=readiness?`<details class="sp-box" ${readiness.checks.some(c=>c.status==='missing'&&!c.optional)?'open':''}><summary>Production connections · ${readiness.checks.filter(c=>c.status==='configured'&&!c.optional).length}/4 configured</summary>${readiness.checks.map(c=>`<p><b>${esc(c.role)}${c.optional?' (optional)':''} · ${esc(c.status)}</b> — ${esc(c.detail)}</p>`).join('')}<p>${esc(readiness.meaning)}</p></details>`:'';
    const learningNode=root.querySelector('#sp-learning'), learning=state.learning||[];
    const learnedSignature=JSON.stringify([shot?.id,learning,shot?.outcomes&&Object.entries(shot.outcomes).map(([k,v])=>[k,v.id,v.status])]);
    if(learningNode&&learningNode.dataset.signature!==learnedSignature){learningNode.dataset.signature=learnedSignature;const approved=['see','hear','watch'].filter(k=>shot?.outcomes?.[k]?.status==='approved');learningNode.innerHTML=`<details class="sp-box"><summary>Project learning</summary><p>Save what worked against an approved outcome. These lessons inform this project; they never become canon or automatic approvals.</p>${approved.length?`<form class="sp-form"><label>Evidence<select name="stage">${approved.map(k=>`<option value="${k}">${k.toUpperCase()} · ${esc(shot.id)}</option>`).join('')}</select></label><label>What should we remember?<textarea name="note" required maxlength="2000"></textarea></label><button class="btn" type="submit">Save project learning</button></form>`:'<p>Approve a picture, voice or render to retain a lesson from it.</p>'}${learning.filter(n=>n.status==='active').map(n=>`<p>${esc(n.note)} · ${esc(n.shotId)} ${esc(n.stage)} <button class="btn ghost" data-retire-learning="${esc(n.id)}">Retire learning</button></p>`).join('')}</details>`;}
    const budget=state.budget;
    const allowanceEditor=root.querySelector('#sp-budget-edit');
    if(allowanceEditor.dataset.allowance!==String(budget.allowance)){allowanceEditor.open=!budget.allowance;allowanceEditor.dataset.allowance=String(budget.allowance);}
    root.querySelector('#sp-budget-form button').textContent=budget.allowance?'Update allowance':'Approve allowance & prepare';
    root.querySelector('#sp-budget-status').textContent=`Allowance ${usd(budget.allowance)} · committed allowance ${usd(budget.committed)} · in progress ${usd(budget.reserved)} · remaining ${usd(budget.allowance-budget.committed-budget.reserved)}`;
    root.querySelector('#sp-cost-evidence')?.remove();
    const costs=ctx.snapshot.costs;
    if(costs)root.querySelector('#sp-budget-status').insertAdjacentHTML('afterend',`<details id="sp-cost-evidence"><summary>Usage and cost evidence</summary><p>${costs.generationJobs||0} generation jobs · ${costs.repeatGenerationJobs||0} repeat jobs for the same shot and stage (includes failed attempts).</p><p>${costs.measuredRequests} requests with measured tokens · ${costs.inputTokens} input / ${costs.outputTokens} output tokens.</p><p>$${Number(costs.estimatedUsd).toFixed(4)} from ${costs.pricedRequests} priced responses. ${costs.unpricedRequests} requests have no verified usage price. This is partial list-price evidence, not your provider invoice. Budget controls retain conservative reservations.</p>${jobs.filter(j=>j.binding).slice(0,8).map(j=>`<p>${esc(j.kind)}${j.shotId?' · '+esc(j.shotId):''} · ${esc(j.binding.model)}${j.binding.route?' · '+esc(j.binding.route):''} · ${esc(j.status)}${j.usage?.estimatedUsd!=null?' · $'+Number(j.usage.estimatedUsd).toFixed(4)+' usage estimate':' · usage price unavailable'}</p>`).join('')}</details>`);
    const last=jobs[0]?.status!=='completed'?jobs[0]:null;
    const jobRoot=root.querySelector('#sp-jobs'),jobSignature=JSON.stringify([last,jobs.filter(j=>j.cleanupPending||j.uploadUnconfirmed)]);
    if(jobRoot.dataset.signature!==jobSignature){jobRoot.dataset.signature=jobSignature;jobRoot.innerHTML=last?`<div class="sp-box"><b>${esc(last.kind==='media_review'?'Media review':last.kind.toUpperCase())} · ${esc(last.status)}</b><p>${esc(last.message||'Working on your outcome…')}</p>${last.progress?`<p class="sp-job-progress">${['failed','unknown','interrupted'].includes(last.status)?'Last recorded step: ':''}${esc(last.progress.label)}${last.progress.total!=null?` · ${last.progress.completed} / ${last.progress.total} clips checked`:''}</p>`:''}${last.audioReview?`<details><summary>Saved audio review</summary><p>${esc(last.audioReview)}</p></details>`:''}${last.taskId?`<small>Provider task ${esc(last.taskId)}</small>`:''}${['pending','interrupted'].includes(last.status)?`<button class="btn ghost" data-resume="${esc(last.id)}">Resume job</button>`:''}${last.status==='unknown'?`<details><summary>Recover an uncertain request</summary><p>Check your provider account first. If a render task exists, enter its ID to resume it. Otherwise close this request; its estimate stays counted.</p>${last.kind==='watch'?'<label>Provider task ID (optional)<input id="sp-recovery-task"></label>':''}<button class="btn ghost" data-reconcile="${esc(last.id)}">I checked the provider — reconcile this request</button></details>`:''}</div>`:'';
    }
    jobRoot.querySelector('.sp-upload-cleanup')?.remove();
    const cleanupJobs=jobs.filter(j=>['failed','completed'].includes(j.status)&&(j.cleanupPending||j.uploadUnconfirmed));
    if(cleanupJobs.length)jobRoot.insertAdjacentHTML('beforeend',`<div class="sp-upload-cleanup">${cleanupJobs.map(j=>`<div class="sp-box"><p>${esc(j.shotId)} · ${j.uploadUnconfirmed?'An upload response was lost; its file ID and deletion cannot be confirmed. Check Gemini Files.':'Temporary Gemini uploads still need cleanup.'}</p>${j.cleanupPending?`<button class="btn ghost" data-cleanup="${esc(j.id)}">Retry upload cleanup</button>`:''}</div>`).join('')}</div>`);
    root.querySelector('#sp-shot-list').innerHTML=state.shots.map(s=>`<button class="btn ${s.id===ctx.shotId?'':'ghost'}" data-shot="${esc(s.id)}" aria-pressed="${s.id===ctx.shotId}">Scene ${s.scene} · ${esc(s.id)}<small>${esc(stage(s)==='done'?'Approved':stage(s).toUpperCase())}</small></button>`).join('');
    root.querySelector('#sp-scope').textContent=shot?`Scene ${shot.scene} · ${shot.id} · ${shot.title}`:'Episode preparation';
    const feed=root.querySelector('#sp-feed'),messages=state.messages.filter(m=>!m.shotId||m.shotId===ctx.shotId);
    const feedSignature=JSON.stringify(messages);
    if(feed.dataset.signature!==feedSignature){feed.innerHTML=messages.map(m=>`<div class="sp-message ${m.role==='user'?'sp-user':''}"><b>${m.role==='user'?'You':'Production agent'}</b><p>${esc(m.text)}</p></div>`).join('')||'<p>Ready when you are. Set your services and episode allowance to begin.</p>';feed.dataset.signature=feedSignature;feed.scrollTop=feed.scrollHeight;}
    if(shot){
    if(ctx.directionShot!==shot.id){ctx.directionManual=false;ctx.directionShot=shot.id;}
      window.StudioDrafts?.bind(root.querySelector('#sp-direction'),[ctx.project.id,ctx.episode,shot.id,'direction'],{
        reset:true,revision:JSON.stringify([shot.sourceSignature,shot.camera,shot.performance,shot.dialogue,Object.values(shot.outcomes||{}).map(o=>[o.id,o.status])]),meta:()=>({stage:root.querySelector('#sp-direction-stage').value,manual:ctx.directionManual}),
        restore:meta=>{if(meta.manual&&['see','hear','watch'].includes(meta.stage)){ctx.directionManual=true;root.querySelector('#sp-direction-stage').value=meta.stage;}}});
      if(!ctx.directionManual)root.querySelector('#sp-direction-stage').value=stage(shot)==='hear'?'hear':['request','watch','done'].includes(stage(shot))?'watch':'see';
    }
    const signature=JSON.stringify([shot||state.shots,ctx.snapshot.review?.coverageBoards]);
    window.StudioReview?.paint(ctx);
    if(ctx.signature===signature){setBusy(ctx,ctx.busy);return;}
    ctx.signature=signature;
    const outcome=root.querySelector('#sp-outcome');
    root.querySelector('#sp-director-card')?.remove();
    root.querySelector('#sp-scene-coverage')?.remove();
    if(!shot){outcome.innerHTML='<div class="sp-box"><h3>Your script becomes directed shots</h3><p>The director prepares emotional beats, camera coverage, performance and matched generation prompts. Your first review is the SEE keyframe.</p><button class="btn" data-command="prepare">Prepare my episode</button></div>';return;}
    const s=stage(shot), candidate=shot.outcomes?.[s];
    let next=s;
    if(candidate?.status==='candidate')next=s==='see'?(shot.dialogue.length?'hear':'request'):s==='hear'?'request':s==='request'?'watch':state.shots.indexOf(shot)<state.shots.length-1?'see':'done';
    const nextRole={see:'keyframes',hear:'voices',watch:'animation'}[next],estimate=ctx.snapshot.review.shots.find(r=>r.id===(next==='see'&&s==='watch'?state.shots[state.shots.indexOf(shot)+1]?.id:shot.id))?.stageEstimates?.[next];
    const nextCost=nextRole?`${candidate?.status==='candidate'?'Approval prepares':'Prepare'} ${next.toUpperCase()} · ${estimate==null?'choose service estimates first':'$'+Number(estimate).toFixed(2)+' estimated'}`:next==='request'?'Next: review the render prompt and references. No generation cost for preparing the request.':'No further generation is needed for this shot.';
    const board=ctx.snapshot.review?.coverageBoards?.find(b=>b.scene===shot.scene);
    const boardHTML=window.StudioCoverage?.html(board);
    if(boardHTML)outcome.insertAdjacentHTML('beforebegin',`<div id="sp-scene-coverage">${boardHTML}</div>`);
    if(shot.directorCard){
      const d=shot.directorCard;
      outcome.insertAdjacentHTML('beforebegin',`<details id="sp-director-card" class="sp-box"><summary>Shot direction · plan, not a footage verdict</summary><p><b>Audience focus:</b> ${esc(d.audienceFocus)}</p><p><b>Camera:</b> ${esc(d.cameraPurpose)}</p><p><b>Cut in / out:</b> ${esc(d.editIn)} / ${esc(d.editOut)}</p>${(d.acting||[]).map(a=>`<p><b>${esc(a.character)}:</b> ${esc(a.intention)} · ${esc(a.attention)}<br>${esc(a.observableBehaviour)}<br>Listening: ${esc(a.listening)}</p>`).join('')}<h4>Planned views</h4><ol>${(d.views||[]).map(v=>`<li><b>${esc(v.entry)} · ${esc(v.framing)}</b> — ${esc(v.audienceNeed)}<br>${esc(v.cutReason)}</li>`).join('')}</ol>${(d.stateChanges||[]).map(c=>`<p><b>${esc(c.subject)}:</b> ${esc(c.before)} → ${esc(c.after)} · ${esc(c.cause)}</p>`).join('')}<p><b>Sound:</b> ${esc(d.soundOwnership)}</p></details>`);
    }
    if(ctx.directionShot!==shot.id){ctx.directionManual=false;ctx.directionShot=shot.id;}
    if(!ctx.directionManual)root.querySelector('#sp-direction-stage').value=s==='hear'?'hear':['request','watch','done'].includes(s)?'watch':'see';
    const media=(item,kind)=>{
      if(!item?.files?.length)return '';
      const url=BASE+'/'+item.files[0].path.split('/').map(encodeURIComponent).join('/');
      return kind==='see'?`<img class="sp-media" src="${esc(url)}" alt="${esc(shot.id)} opening keyframe">`:kind==='hear'?`<audio class="sp-media" controls preload="metadata" src="${esc(url)}"></audio>`:`<video class="sp-media" controls preload="metadata" src="${esc(url)}"></video>`;
    };
    outcome.innerHTML=`<div class="sp-shot-heading"><span class="lab">Scene ${shot.scene} · ${esc(shot.id)}</span><h3>${esc(shot.title)}</h3><p>${esc(shot.emotion)}</p>${shot.intent?`<p><b>Character wants:</b> ${esc(shot.intent)}</p>`:''}</div>${shot.continuityReview?`<p class="sp-notice">${esc(shot.continuityReview)}</p>`:''}<div class="sp-step-labels">${['see','hear','request','watch'].map(k=>`<span class="${s===k?'current':''}">${k==='request'?'Render request':k.toUpperCase()} · ${esc(shot.outcomes?.[k]?.status||(k==='hear'&&!shot.dialogue.length?'No dialogue':'Next'))}</span>`).join('')}</div>
      ${['see','hear','watch'].filter(k=>shot.outcomes?.[k]).map(k=>`<details class="sp-box" ${(k===s||s==='done'&&k==='watch')?'open':''}><summary>${k.toUpperCase()} · ${esc(shot.outcomes[k].status)}</summary>${k==='see'&&(shot.outcomes[k].references||[]).find(r=>r.name.startsWith('Previous approved ending'))?`<figure><figcaption>Incoming approved ending · continuity reference</figcaption><img class="sp-media" src="${esc(BASE+'/'+shot.outcomes[k].references.find(r=>r.name.startsWith('Previous approved ending')).path)}" alt="Previous approved ending"></figure>`:''}${media(shot.outcomes[k],k)}${k==='see'&&shot.outcomes[k].shotRemix?`<details class="sp-box" open><summary>SEE · Shot Remix</summary><p>${esc(shot.outcomes[k].shotRemix.previousShotId)} → ${esc(shot.id)} · ${esc(shot.outcomes[k].shotRemix.cutType.replaceAll('_',' '))}</p><p>${esc(shot.outcomes[k].shotRemix.continuityEvidence)} · Visual continuity awaits your review.</p><p>${esc(shot.outcomes[k].shotRemix.camera)}</p><p>Check identity, world positions, eyelines, prop ownership, contact and lighting. Unseen geography remains provisional.</p><div class="sp-references">${shot.outcomes[k].shotRemix.references.map(r=>`<figure><img src="${esc(BASE+'/'+r.path.split('/').map(encodeURIComponent).join('/'))}" alt="${esc(r.name)}"><figcaption>${esc(r.name)} · ${esc(r.role)} · ${esc(r.approvalStatus)}<br>${esc(shot.outcomes[k].shotRemix.authority[r.role]||r.description||'')}</figcaption></figure>`).join('')}</div><p>Change the camera or opening beat through shot direction below.</p></details>`:''}${shot.outcomes[k].audioAuthority?`<p>${esc(shot.outcomes[k].audioAuthority.note)}</p>`:''}</details>`).join('')}
      ${shot.outcomes?.request?`<details class="sp-box" ${s==='request'?'open':''}><summary>WATCH request · ${shot.outcomes.request.duration}s · ${esc(shot.outcomes.request.resolution)} · $${Number(shot.outcomes.request.estimateUsd??shot.outcomes.request.binding.estimateUsd).toFixed(2)} estimated</summary><p>Model: ${esc(shot.outcomes.request.binding.model)}</p>${shot.outcomes.request.promptDirector?`<h4>Prompt Director · ${esc(shot.outcomes.request.promptDirector.verdict)}</h4><p>${esc(shot.outcomes.request.promptDirector.summary)}</p><p>${esc(shot.outcomes.request.promptDirector.camera)}</p><p>${esc(shot.outcomes.request.promptDirector.audio)}</p><details><summary>Continuity evidence and risks</summary><pre>${esc(JSON.stringify({lifecycle:shot.outcomes.request.promptDirector.lifecycle,findings:shot.outcomes.request.promptDirector.findings,corrections:shot.outcomes.request.promptDirector.trace},null,2))}</pre></details>`:''}<details><summary>Exact final prompt</summary><pre>${esc(shot.outcomes.request.prompt)}</pre></details><h4>Script</h4><pre>${esc(shot.outcomes.request.source)}</pre><button class="btn ghost" data-command="request">Refresh request for review</button><h4>References</h4><div class="sp-references">${shot.outcomes.request.images.map(r=>`<figure><img src="${esc(BASE+'/'+r.path)}" alt="${esc(r.name)}"><figcaption>${esc(r.name)}</figcaption></figure>`).join('')}</div></details>`:''}
      <div class="sp-actions">${s==='done'?'<p>Render approved. Select the next shot.</p>':candidate?.status==='candidate'?`<button class="btn" data-command="approve">${s==='request'?'Approve request & render':'Approve '+s.toUpperCase()+' & continue'}</button><button class="btn ghost" data-command="reject">Reject ${s==='request'?'request':s.toUpperCase()}</button>`:`<button class="btn" data-command="${s==='watch'?'watch':'continue'}">${s==='watch'?'Render approved request':'Prepare '+(s==='request'?'WATCH request':s.toUpperCase())}</button>`}</div>
      ${s!=='done'?'<label>Review note (optional)<textarea id="sp-review-note" placeholder="What should improve?"></textarea></label>':''}
      <details class="sp-box"><summary>Direction, source and shot history</summary><p><b>Acting:</b> ${esc(shot.performance)}</p><p><b>Camera:</b> ${esc(shot.camera)}</p><p><b>Geography:</b> ${esc(shot.geography)}</p><p><b>Handoff:</b> ${esc(shot.transition)}</p><p><b>Opening state:</b> ${esc(shot.openingState||shot.geography)}</p><p><b>Ending state:</b> ${esc(shot.endingState||'See the recorded handoff direction.')}</p>${shot.beatPlan?.length?`<h4>Performance beats</h4><ol>${shot.beatPlan.map(b=>`<li>${b.at}s · ${esc(b.action)} — ${esc(b.audienceFeeling)}</li>`).join('')}</ol>`:''}<h4>SEE prompt</h4><pre>${esc(shot.seePrompt)}</pre><h4>WATCH prompt</h4><pre>${esc(shot.watchPrompt)}</pre><h4>Exact dialogue</h4><pre>${esc(shot.dialogue.map(d=>d.speaker+': '+d.text).join('\n'))}</pre><p>${shot.versions?.length||0} previous outcome versions retained.</p>${(shot.versions||[]).map(v=>`<details><summary>${esc(v.stage.toUpperCase())} · ${esc(v.status)}</summary>${media(v,v.stage)}</details>`).join('')}</details>`;
    setBusy(ctx,ctx.busy);
    window.StudioDrafts?.bind(root.querySelector('#sp-review-note'),[ctx.project.id,ctx.episode,shot.id,candidate?.id||s,'review-note'],{revision:candidate?.id||s,reset:true});
    if(!shot.importedArchive)outcome.querySelector('.sp-actions').insertAdjacentHTML('afterend',`<p class="sp-next-cost">${esc(nextCost)}</p>`);
    root.querySelector('#sp-chat').hidden=!!shot.importedArchive;
    if(shot.importedArchive){outcome.querySelector('.sp-step-labels').innerHTML='<span>Preserved production archive</span>';outcome.querySelector('.sp-actions').innerHTML=`<p>Its original approval evidence and files remain available.</p><a class="btn ghost" href="${esc(BASE+'/'+shot.legacy.package.path)}" download>Original production record</a>`;for(const box of outcome.querySelectorAll('details'))if(box.querySelector('video'))box.open=true;}
  }
  async function migration(projectId) {
    const root=modal('Move into the director workspace');root.textContent='Checking source records and approval evidence…';
    try {
      const report=await api('/api/project-migration?projectId='+encodeURIComponent(projectId));if(!root.isConnected)return;
      root.innerHTML=`<p>${esc(report.meaning)}</p><p>${report.characters} characters · ${report.files} files · ${(report.bytes/1024/1024).toFixed(0)} MB to copy</p><ul>${report.episodes.map(e=>`<li>Episode ${e.number}: ${esc(e.title)} · ${e.approvedShots} verified approved shots / ${e.shots} records</li>`).join('')}</ul>${report.warnings.length?`<details open><summary>${report.warnings.length} items to review</summary><ul>${report.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></details>`:''}<p>Imported episodes stay as production archives. New episodes use the project agent. Choose services in the new workspace; API credentials are not copied.</p><form class="sp-form"><label>New workspace ID<input name="target" value="${esc(report.suggestedId)}" required></label><label><input type="checkbox" name="reviewed" required style="width:auto"> I have reviewed what will be copied and the items needing attention</label><button class="btn" type="submit">Create upgraded workspace</button><p data-error role="alert"></p></form>`;
      const form=root.querySelector('form');form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;button.textContent='Copying and verifying…';try{await api('/api/project-migration',{projectId,targetId:form.elements.target.value,fingerprint:report.fingerprint,reviewed:form.elements.reviewed.checked});document.getElementById('modal').classList.remove('show');await bootProjects();}catch(error){showError(root,error.message);button.disabled=false;button.textContent='Create upgraded workspace';}};
    } catch(error){showError(root,error.message);}
  }
  window.StudioProduction={mount,connections,services,library,states,importScript,migration};
})();
