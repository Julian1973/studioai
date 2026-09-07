/* Episode-level end credits, independent of scene review state. */
(() => {
  let dialog, episode, state, poll, busy = false, token = null, displayKey = '', edited = false;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const active = s => ['starting','submitting','queued','running','downloading','compositing'].includes(s);
  const api = async body => {
    const response = await fetch(BASE + '/api/credits' + (body ? '' : '?episode='+encodeURIComponent(episode)), {
      cache:'no-store', priority:'high', ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({episode,...body})} : {})
    });
    const data = await response.json();
    if (!response.ok || data.error && !data.ok) throw new Error(data.error || 'The credits request failed.');
    return data;
  };
  function message(text) { dialog.querySelector('[data-message]').textContent = text; }
  function config() {
    return {title:dialog.querySelector('[name=title]').value,
      character:dialog.querySelector('[name=character]').value,
      background:dialog.querySelector('[name=background]').value,
      cards:Array.from(dialog.querySelectorAll('[data-credit-card]')).map(el => [el.querySelector('input').value,el.querySelector('textarea').value])};
  }
  function dirty() {
    token = null; edited = true;
    dialog.querySelector('[data-fire]')?.setAttribute('disabled','');
    message('Preview to save these choices and check the render cost.');
    const selected = state.characters.find(x => x.name === dialog.querySelector('[name=character]').value);
    if (selected) dialog.querySelector('[data-character-image]').src = BASE + selected.reference;
  }
  function controls() {
    const waiting = active(state.status) || state.status === 'interrupted';
    dialog.querySelector('fieldset').disabled = busy || waiting;
    dialog.querySelector('[data-prepare]').disabled = busy || waiting;
  }
  function statusPanel() {
    controls();
    const key = [state.id,state.status,state.videoUrl,state.previewUrl,state.canResume].join('|');
    if (key === displayKey) return;
    displayKey = key;
    const region = dialog.querySelector('[data-result]');
    token = state.status === 'prepared' && !edited ? state.token : null;
    if (state.status === 'prepared') {
      const d = state.disclosure;
      region.innerHTML = `<h3>Ready to create</h3><img class="credits-preview" src="${BASE}${esc(state.previewUrl)}" alt="Exact Bangers title and first credit card"><p>30 seconds · one ${esc(d.provider)} render · ${esc(d.resolution)} · silent</p><p><b>Estimated cost: $${Number(d.maxBatchCostUsd).toFixed(2)}</b></p><button class="btn" data-fire ${edited?'disabled':''}>Create 30-second credits · $${Number(d.maxBatchCostUsd).toFixed(2)}</button>`;
      region.querySelector('[data-fire]').onclick = () => action('fire',{token});
    } else if (active(state.status)) {
      const labels = {starting:'Starting the credits job…',submitting:'Submitting to Seedance…',queued:'Queued with Seedance…',running:'Animating your presenter…',downloading:'Downloading the animation…',compositing:'Adding the official fonts and exact credits…'};
      region.innerHTML = `<h3>${labels[state.status]}</h3><p>The result will appear here when ready. You can close this panel and reopen it later.</p>${state.providerTaskId?`<small>Job ${esc(state.providerTaskId)}</small>`:''}`;
    } else if (['awaiting_review','accepted','rejected'].includes(state.status)) {
      const heading = state.status==='accepted'?'End credits accepted':state.status==='rejected'?'Credits marked for another version':'Review your end credits';
      region.innerHTML = `<h3>${heading}</h3><video class="credits-preview" controls playsinline src="${BASE}${esc(state.videoUrl)}"></video><p>Check the character, presenting gestures and text clearance. Add your soundtrack in the edit.</p><a class="btn ghost" download href="${BASE}${esc(state.videoUrl)}">Download 30-second credits</a>${state.status==='awaiting_review'?'<button class="btn" data-accept>Accept these credits</button><button class="btn ghost" data-reject>Make another version</button>':''}`;
      region.querySelector('[data-accept]')?.addEventListener('click',()=>action('accept',{id:state.id}));
      region.querySelector('[data-reject]')?.addEventListener('click',()=>action('reject',{id:state.id}));
    } else if (state.status === 'interrupted' || state.status === 'failed') {
      region.innerHTML = `<h3>Credits need attention</h3><p>${esc(state.error || 'The worker stopped.')}</p>${state.canResume?'<button class="btn" data-resume>Resume existing job · no new render</button>':''}`;
      region.querySelector('[data-resume]')?.addEventListener('click',()=>action('resume'));
    } else region.innerHTML = '';
  }
  async function action(name, payload={}) {
    if (busy || name==='fire'&&!payload.token) return;
    busy=true;controls();
    dialog.querySelectorAll('[data-result] button').forEach(b=>b.disabled=true);
    message(name==='prepare'?'Saving choices and preparing the preview…':name==='fire'?'Submitting your approved render…':'Saving…');
    try { state=await api({action:name,...payload});if(name==='prepare')edited=false;displayKey='';message(''); }
    catch (error) { message(error.message); }
    finally { busy=false;displayKey='';statusPanel(); }
  }
  async function tick() {
    if (!dialog?.open) return;
    if (!busy) try { const next=await api(); if (!dialog.open) return; state=next;statusPanel(); }
      catch (error) { message('Connection interrupted. Your existing job is preserved. '+error.message); }
    poll=setTimeout(tick,4000);
  }
  window.openCreditsMaker = async function(ep) {
    episode = ep || SH_EP || (CUR?.number ? 'Ep'+CUR.number : '');
    if (!episode) return;
    clearTimeout(poll);
    if (!dialog) {
      dialog=document.createElement('dialog');dialog.id='creditsMaker';
      dialog.className='credits-maker';document.body.appendChild(dialog);
      dialog.addEventListener('close',()=>clearTimeout(poll));
    }
    dialog.innerHTML='<button class="btn ghost" onclick="this.closest(\'dialog\').close()">Close</button><p>Loading end credits…</p>';
    if (!dialog.open) dialog.showModal();
    busy=false;displayKey='';edited=false;
    try {
      state=await api();
      const c=state.config || {...state.defaults,title:(CUR?.title || state.defaults.title).replace(/\s+V\d+$/i,'')};
      const choice=state.characters.find(x=>x.name===c.character)||state.characters[0];
      dialog.innerHTML=`<header><div><small>${esc(episode.replace('Ep','Episode '))} · End credits</small><h2>Who presents the credits?</h2></div><button class="btn ghost" data-close aria-label="Close end credits">Close</button></header>
        <p>Choose a character and background. Your presenter introduces seven credit cards over 30 seconds, with the official fonts. The video is silent for you to add the soundtrack later.</p>
        <fieldset><div class="credits-choices"><label>Character<select name="character">${state.characters.map(x=>`<option value="${esc(x.name)}" ${x.name===c.character?'selected':''}>${esc(x.label)}</option>`).join('')}</select></label><label>Background colour<input type="color" name="background" value="${esc(c.background)}"></label></div>
        <img data-character-image class="credits-character" src="${BASE}${esc(choice?.reference||'')}" alt="Approved character reference">
        <label>Episode title<input name="title" maxlength="100" value="${esc(c.title)}"></label>
        <details><summary>Review names and credits</summary>${c.cards.map((row,i)=>`<div data-credit-card><label>${['0–4','4–8','8–12','12–17','17–21','21–26','26–30'][i]} seconds<input aria-label="Credit ${i+1} heading" maxlength="70" value="${esc(row[0])}"></label><textarea aria-label="Credit ${i+1} names" maxlength="220" rows="3">${esc(row[1])}</textarea></div>`).join('')}</details></fieldset>
        <button class="btn" data-prepare>Preview credits &amp; cost</button><p data-message role="status" aria-live="polite"></p><section data-result aria-live="polite"></section>`;
      dialog.querySelector('[data-close]').onclick=()=>dialog.close();
      dialog.querySelector('[data-prepare]').onclick=()=>action('prepare',{config:config()});
      dialog.querySelector('fieldset').addEventListener('input',dirty);
      statusPanel();poll=setTimeout(tick,4000);
    } catch(error) {dialog.innerHTML=`<h2>End credits</h2><p>${esc(error.message)}</p><button class="btn" onclick="this.closest('dialog').close()">Close</button>`;}
  };
  window.creditsEpisodeCompletion = function() {
    const rows=BOARD_SCENES||[];
    const ep=SH_EP || (CUR?.number?'Ep'+CUR.number:'');
    if (!ep || !rows.length || !rows.every(s=>s.stages?.final?.state==='approved')) return;
    const key='credits_completion_prompt_'+ep;
    if (!sessionStorage.getItem(key)) {sessionStorage.setItem(key,'1');openCreditsMaker(ep);}
  };
})();
