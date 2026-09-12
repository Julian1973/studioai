/* The normal producer surface. Technical routes remain in the evidence drawer. */
(function(global){
'use strict';
let sequence=0;
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
async function api(body){const r=await fetch('/api/production-journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Studio could not load the current production action.');return data;}
function mount(host,scope,options={}){
 const scopeId=JSON.stringify(scope);if(host.journeyHandle?.scopeId===scopeId){host.journeyHandle.refresh();return host.journeyHandle;}host.journeyHandle?.();
 const ticket=++sequence;let state=null,timer=null,submitted=false,awaitingNext=false,mediaSignature=null,settledSignature=null;
 host.replaceChildren();host.classList.add('journey-workspace');
 const head=node('div',undefined,'journey-head'),title=node('h2',scope.unit),progress=node('p','Loading current production…');
 head.append(title,progress);const media=node('div',undefined,'journey-media'),brief=node('div',undefined,'journey-brief');
 const actions=node('div',undefined,'journey-actions'),primary=node('button','Loading…','btn'),changes=node('button','Request Changes','btn ghost');primary.disabled=true;
 const cost=node('p',undefined,'journey-cost'),issue=node('div',undefined,'journey-issue');issue.setAttribute('role','status');progress.setAttribute('aria-live','polite');
 const evidence=node('details'),summary=node('summary','Direction, references and evidence'),evidenceBody=node('pre');evidence.append(summary,evidenceBody);
 const advanced=node('details'),advancedTitle=node('summary','Individual corrections and review tools');advanced.append(advancedTitle);
 if(options.advanced){advanced.addEventListener('toggle',()=>{if(advanced.open&&!advanced.dataset.loaded){advanced.dataset.loaded='1';options.advanced(advanced);}});}
 changes.onclick=()=>options.changes?.(state);
 actions.append(primary,changes);host.append(head,media,brief,issue,cost,actions,evidence);if(options.advanced)host.append(advanced);
 function asset(record,type){if(!record?.url)return;const e=node(type);e.src=record.url;if(type==='img'){e.alt=(record.label||'Opening image')+' for '+scope.unit;}else{e.controls=true;e.preload='metadata';}const figure=node('figure');if(record.label)figure.append(node('figcaption',record.label));figure.append(e);media.append(figure);}
 function show(value){
  state=value;if(state.busy&&state.operation?.phase==='film')awaitingNext=true;const op=state.operation,review=state.review||{};
  title.textContent=scope.unit+' · '+(review.title||'Scene production');
  progress.textContent=state.busy?(op?.message||'Preparing your next review'):state.phase==='complete'?'Accepted · ready for the next unit':state.primary||state.dependency||'Review the current issue';
  const nextMediaSignature=JSON.stringify([state.phase,review.videos,review.images,review.audio,review.plan]);
  if(nextMediaSignature!==mediaSignature){mediaSignature=nextMediaSignature;media.replaceChildren();
  if(state.phase==='film'||state.phase==='complete'){for(const r of review.videos||[])asset(r,'video');}
  else if(state.phase==='audio'){asset(review.audio,'audio');for(const r of review.images||[])asset(r,'img');}
  else if(review.images?.length&&state.phase!=='plan'){for(const r of review.images)asset(r,'img');}
  else{
   const views=Array.isArray(review.plan)?review.plan:Object.values(review.plan||{}).flat();
   for(const view of views){if(!view||typeof view!=='object')continue;const card=node('article',undefined,'journey-board');card.append(node('small','Storyboard plan · placeholder'),node('h3',view.viewId||view.shotId||'Planned view'),node('p',view.action||view.purpose||view.openingImage||view.staging||''),node('p',view.framing||view.camera||''),node('p',view.performance||''));media.append(card);}
   if(!media.childElementCount)media.append(node('p','Prepare the scene to review its direction and storyboard.'));
  }
  }
  brief.replaceChildren();if(review.direction)brief.append(node('p',review.direction));
  if(['audio','film'].includes(state.phase)&&review.actionPlan?.length){brief.append(node('h3','Action'));for(const beat of review.actionPlan){brief.append(node('p',(beat.timing?beat.timing+' · ':'')+beat.action));}}
  for(const line of review.script||[]){const p=node('p');p.append(node('b',(line.speaker||'')+' '),node('em','“'+(line.exactText||line.text||line.words||'')+'”'));brief.append(p);}
  if(state.phase==='audio'&&review.performancePrompt){const p=node('details');p.append(node('summary','ElevenLabs performance prompt'),node('pre',review.performancePrompt));brief.append(p);}
  const decision=op?.status==='needs-decision'?op.decision:null;
  issue.replaceChildren();if(op?.status==='superseded'&&op.decision){issue.append(node('strong',op.decision.issue),node('p',op.decision.proposed));}if(decision){issue.append(node('strong',decision.issue),node('p',decision.proposed),node('p','Preserved: '+(decision.preserved||[]).join(', ')));}
  for(const concern of state.concerns||[]){issue.append(node('p',typeof concern==='string'?concern:concern.message||concern.observation||''));}
  cost.textContent=state.disclosure?.limitUsd?'Authorises '+(state.disclosure.operations||[]).join(', ')+' · up to $'+state.disclosure.limitUsd.toFixed(2)+'. '+(state.disclosure.basis||''):'No new generation cost.';
  primary.textContent=state.busy?(op?.message||'Working…'):state.primary||'Waiting for the required decision';
  primary.hidden=state.phase==='complete';
  primary.disabled=state.busy||(!state.primary&&!decision)||submitted;
  if(decision)primary.textContent='Check saved operation';
  changes.disabled=state.busy||!options.changes;
  evidenceBody.textContent=JSON.stringify({scope,state:state.phase,normalActions:state.normalActionCount,corrections:state.correctionActionCount,review,operation:op,qualification:'Software checks do not establish live visual compliance.'},null,2);
  const settledKey=op&&!state.busy?[op.id,op.status].join(':'):null;if(settledKey&&settledKey!==settledSignature){settledSignature=settledKey;options.settled?.(state);}
  if(awaitingNext&&state.phase==='complete'&&state.next&&options.next){awaitingNext=false;options.next(state.next);return;}
 }
 async function refresh(resume=false){clearTimeout(timer);if(ticket!==sequence||!host.isConnected)return;try{show(await api({command:resume?'resume':'status',scope}));if(state.busy)timer=setTimeout(()=>refresh(true),1800);}catch(e){issue.textContent=e.message;primary.disabled=true;}}
 primary.onclick=async()=>{if(!state||submitted||primary.disabled)return;submitted=true;if(state.operation?.status==='needs-decision'){try{show(await api({command:'recover',scope}));}catch(e){issue.textContent=e.message;}finally{submitted=false;refresh(true);}return;}awaitingNext=state.phase==='film';primary.disabled=true;progress.textContent='Starting '+state.primary+'…';try{show(await api({command:'decide',scope,action:state.phase,binding:state.binding,expectedRevision:state.revision,commandId:crypto.randomUUID(),by:options.reviewer||'Producer'}));}catch(e){issue.textContent=e.message;}finally{submitted=false;if(ticket===sequence)refresh(true);}};
 const handle=()=>{clearTimeout(timer);if(ticket===sequence)sequence++;};handle.scopeId=scopeId;handle.refresh=()=>refresh(true);host.journeyHandle=handle;refresh(true);return handle;
}
global.StudioJourney={mount};
})(window);
