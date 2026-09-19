/* The normal producer surface. Technical routes remain in the evidence drawer. */
(function(global){
'use strict';
let sequence=0;
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
async function api(body){const r=await fetch('/api/production-journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok||data.ok===false){const e=data.error||{};const detail=[e.errorCode&&`errorCode=${e.errorCode}`,e.stage&&`stage=${e.stage}`,e.operation&&`operation=${e.operation}`,e.technicalMessage&&`error=${e.technicalMessage}`,e.humanMessage||e.message].filter(Boolean).join('\n');throw new Error(detail||'Studio could not load the current production action.');}return data;}
function mount(host,scope,options={}){
 const scopeId=JSON.stringify(scope);if(host.journeyHandle?.scopeId===scopeId){host.journeyHandle.refresh();return host.journeyHandle;}host.journeyHandle?.();
 const ticket=++sequence;let state=null,timer=null,submitted=false,awaitingNext=false,mediaSignature=null,settledSignature=null;
 host.replaceChildren();host.classList.add('journey-workspace');
 const head=node('div',undefined,'journey-head'),title=node('h2',scope.unit),progress=node('p','Loading current production…');
 head.append(title,progress);const media=node('div',undefined,'journey-media'),storyboard=node('section',undefined,'journey-storyboard'),brief=node('div',undefined,'journey-brief');
 const actions=node('div',undefined,'journey-actions'),primary=node('button','Loading…','btn'),changes=node('button','Edit / Request Changes','btn ghost');primary.disabled=true;
 const cost=node('p',undefined,'journey-cost'),issue=node('div',undefined,'journey-issue');issue.setAttribute('role','status');progress.setAttribute('aria-live','polite');
 const evidence=node('details'),summary=node('summary','Direction, references and evidence'),evidenceBody=node('pre');evidence.append(summary,evidenceBody);
 const advanced=node('details'),advancedTitle=node('summary','Individual corrections and review tools');advanced.append(advancedTitle);
 if(options.advanced){advanced.addEventListener('toggle',()=>{if(advanced.open&&!advanced.dataset.loaded){advanced.dataset.loaded='1';options.advanced(advanced);}});}
 changes.onclick=()=>options.changes?.(state);
 actions.append(primary,changes);actions.setAttribute('aria-label','Next required action');host.append(head,actions,issue,cost,media,storyboard,brief,evidence);if(options.advanced)host.append(advanced);
 function imageAsset(record){
  if(!record?.url)return;
  const card=node('article',undefined,'journey-image-card'),figure=node('figure');
  const image=node('img');image.src=record.url;image.alt=(record.label||'SEE image')+' for '+scope.unit;
  figure.append(node('figcaption',record.label||'SEE image'),image);card.append(figure);
  const status=node('p',record.reviewStatus==='approved'?'Approved':record.reviewStatus==='pending'?'Awaiting decision':record.reviewStatus==='stale'?'Refresh required':'Needs image');status.className='journey-image-status';
  const controls=node('div',undefined,'journey-image-actions');
  const decisions=record.component==='plate'
   ?[['approved','Approve'],['rejected','Reject']]
   :[['approved','Approve'],['rejected','Reject'],['refire','Refire']];
  for(const [action,label] of decisions){
   const button=node('button',label,'btn '+(action==='refire'?'ghost':''));
   button.type='button';button.setAttribute('aria-label',label+' '+(record.label||'SEE image'));
   button.disabled=action==='approved'&&record.reviewStatus!=='pending'||action==='rejected'&&record.reviewStatus!=='pending';
   button.onclick=async()=>{
    if(!options.imageAction||button.disabled)return;
    let reason='';
    if(action==='rejected'){reason=window.prompt('Reason for rejecting '+(record.label||'this image')+':','Needs a different SEE treatment.');if(reason===null||!reason.trim())return;}
    controls.querySelectorAll('button').forEach(item=>{item.disabled=true;});status.textContent=action==='refire'?'Opening refire controls…':'Saving '+label.toLowerCase()+'…';
    try{const result=await options.imageAction({action,component:record.component,reason,record,state});status.textContent=result?.message||label+' recorded';}
    catch(error){status.textContent=error.message||'Image action failed';controls.querySelectorAll('button').forEach(item=>{item.disabled=false;});}
   };
   controls.append(button);
  }
  card.append(status,controls);media.append(card);
  if(record.component==='plate'&&options.scenePlateAction){
   const sourceControls=node('div',undefined,'journey-image-source-actions');
   const upload=node('button','Upload','btn ghost');upload.type='button';
   const input=document.createElement('input');input.type='file';input.accept='image/png,image/jpeg,image/webp';input.hidden=true;
   upload.onclick=()=>input.click();
   input.onchange=async()=>{
    if(!input.files?.length)return;
    sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=true;});
    status.textContent='Installing uploaded Scene Plate…';
    try{const result=await options.scenePlateAction({action:'upload',input,record,state});status.textContent=result?.message||'Uploaded Scene Plate is ready for approval';}
    catch(error){status.textContent=error.message||'Scene Plate upload failed';}
    finally{sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=false;});}
   };
   const refire=node('button','Refire','btn ghost');refire.type='button';
   refire.onclick=async()=>{
    sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=true;});
    try{const result=await options.scenePlateAction({action:'refire',record,state});status.textContent=result?.message||'Refire controls opened';}
    catch(error){status.textContent=error.message||'Scene Plate refire could not be opened';sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=false;});}
   };
   const library=node('button','Library','btn ghost');library.type='button';
   library.onclick=async()=>{
    sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=true;});
    try{const result=await options.scenePlateAction({action:'library',record,state});status.textContent=result?.message||'Scene Plate library opened';}
    catch(error){status.textContent=error.message||'Scene Plate library could not be opened';}
    finally{sourceControls.querySelectorAll('button').forEach(item=>{item.disabled=false;});}
   };
   sourceControls.append(upload,refire,library,input);card.append(sourceControls);
  }
}
 function asset(record,type){if(!record?.url)return;const e=node(type);e.src=record.url;if(type==='img'){e.alt=(record.label||'Opening image')+' for '+scope.unit;}else{e.controls=true;e.preload='metadata';}const figure=node('figure');if(record.label)figure.append(node('figcaption',record.label));figure.append(e);media.append(figure);}
 function renderStoryboard(review){
  storyboard.replaceChildren();const views=Array.isArray(review.storyboard)&&review.storyboard.length?review.storyboard:(Array.isArray(review.plan)?review.plan:Object.values(review.plan||{}).flat());
  const heading=node('div',undefined,'journey-storyboard-head'),title=node('h3','Storyboard · visual board','journey-storyboard-title'),controls=node('div',undefined,'journey-storyboard-actions');
  const choice=review.storyboardChoice, required=choice==null||choice.required!==false;
  const state=node('span',required?'Storyboard on':'Storyboard skipped','journey-storyboard-state');
  for(const [value,label] of [[true,'Use storyboard'],[false,'Skip storyboard']]){
   const button=node('button',label,'btn '+(value?'':'ghost'));button.type='button';button.disabled=required===value;
   button.onclick=async()=>{if(!options.storyboardAction||button.disabled)return;controls.querySelectorAll('button').forEach(item=>{item.disabled=true;});try{await options.storyboardAction({required:value,review});}catch(error){state.textContent=error.message||'Storyboard choice failed';controls.querySelectorAll('button').forEach(item=>{item.disabled=false;});}};
   controls.append(button);
  }
  const seePackage=review.seePackage||{}, sheet=seePackage.providerSheet?.media, gridAllowed=review.storyboardRequired!==false;
  const imageRecords=Array.isArray(review.images)?review.images:[], plateApproved=imageRecords.some(item=>item?.component==='plate'&&item.reviewStatus==='approved'), openingApproved=imageRecords.some(item=>item?.component==='opening'&&item.reviewStatus==='approved');
  const gridIssues=Array.isArray(seePackage.issues)?seePackage.issues.filter(Boolean):[], stalePlate=imageRecords.some(item=>item?.component==='plate'&&item.reviewStatus==='stale'), approvalBlock=!plateApproved?(stalePlate?'Refresh scene plate first':'Approve scene plate first'):!openingApproved?'Approve opening keyframe first':'', gridBlocked=gridIssues.length>0||!!approvalBlock;
  const gridLabel=sheet?'Storyboard grid ready':!gridAllowed?'Storyboard skipped':gridIssues.length?'Resolve SEE issue first':approvalBlock||'Build Seedance storyboard grid';
  const gridButton=node('button',gridLabel,'btn ghost');gridButton.type='button';gridButton.dataset.storyboardGrid='1';gridButton.disabled=!!sheet||!options.storyboardGridAction||!gridAllowed||gridBlocked;if(gridBlocked)gridButton.title=String(gridIssues[0]||approvalBlock);
  if(options.storyboardGridAction&&!sheet){gridButton.onclick=async()=>{gridButton.disabled=true;gridButton.textContent='Building storyboard grid…';try{await options.storyboardGridAction({review});}catch(error){gridButton.disabled=false;gridButton.textContent=error.message||'Build Seedance storyboard grid';}};}
  controls.append(gridButton);
  if(gridBlocked&&!sheet)controls.append(node('small','Grid blocked · '+String(gridIssues[0]||approvalBlock),'journey-storyboard-grid-note'));
  heading.append(title,state,controls);storyboard.append(heading);
  if(sheet?.url){const grid=node('figure',undefined,'journey-storyboard-grid');const image=node('img');image.src=sheet.url;image.alt='Chronological Seedance storyboard grid';grid.append(image,node('figcaption','Seedance reference · read left to right, then top to bottom'));storyboard.append(grid);}
  const sourceImages=(review.images||[]).filter(record=>record?.url).sort((a,b)=>({plate:0,opening:1}[a.component]??2)-({plate:0,opening:1}[b.component]??2));
  const references=(Array.isArray(seePackage.referenceInputs)?seePackage.referenceInputs:[]).filter(record=>record?.url&&/\.(?:png|jpe?g|webp|gif)(?:[?#]|$)/i.test(record.url));
  const inputs=references.length?references:[...sourceImages,...Object.values(review.references||{}).flatMap(section=>Array.isArray(section?.references)?section.references:[]).filter(record=>record?.url&&/\.(?:png|jpe?g|webp|gif)(?:[?#]|$)/i.test(record.url)).filter(record=>!sourceImages.some(source=>source.url===record.url))];
  if(inputs.length){
   const inputSection=node('section',undefined,'journey-storyboard-inputs');
   inputSection.append(node('h4','Visual inputs','journey-storyboard-input-title'));
   const inputGrid=node('div',undefined,'journey-storyboard-input-grid');
   for(const record of inputs.slice(0,8)){
    const figure=node('figure',undefined,'journey-storyboard-input');const image=node('img');image.src=record.url;image.alt=record.label||record.role||'Storyboard reference';
    figure.append(image,node('figcaption',record.label||record.role||'Reference'));inputGrid.append(figure);
   }
   inputSection.append(inputGrid);storyboard.append(inputSection);
  }
  if(!views.length){storyboard.append(node('p','No storyboard panels prepared for this production unit.','journey-storyboard-empty'));return;}
  const panelSources=sourceImages.length?sourceImages:references;
  const cameraText=view=>view.framing||view.framingAndCamera||view.camera||view.cameraBehaviour||view.cameraBehavior||'';
  const movementText=view=>view.cameraPurpose||view.movement||view.action||view.staging||'';
  for(const [index,view] of views.entries()){
   if(!view||typeof view!=='object')continue;
   const card=node('article',undefined,'journey-board journey-visual-board'),frame=node('div',undefined,'journey-board-frame');
   const source=panelSources[index===0?0:Math.min(1,panelSources.length-1)]||panelSources[index%Math.max(panelSources.length,1)];
   if(source?.url){const image=node('img');image.src=source.url;image.alt='Visual storyboard panel '+(index+1);frame.append(image);}
   frame.append(node('span','Panel '+(view.storyboardIndex||index+1),'journey-board-index'));card.append(frame);
   const details=node('div',undefined,'journey-board-details');details.append(node('small',view.viewId||view.shotId||'Planned view'),node('h4',view.action||view.purpose||'Planned visual beat'));
   const camera=cameraText(view),movement=movementText(view),performance=view.performance||view.performanceFocus||'';
   if(camera)details.append(node('p','Camera: '+camera));
   if(movement&&movement!==camera)details.append(node('p','Movement: '+movement));
   if(performance)details.append(node('p','Performance: '+performance));
   card.append(details);storyboard.append(card);
  }
 }
 function show(value){
  const previousPhase=state?.phase;state=value;if(state.busy&&state.operation?.phase==='film')awaitingNext=true;const op=state.operation,review=state.review||{};
  title.textContent=scope.unit+' · '+(review.title||'Scene production');
  progress.textContent=state.busy?(op?.message||'Preparing your next review'):state.phase==='complete'?'Accepted · ready for the next unit':state.primary||state.dependency||'Review the current issue';
  const images=[...(review.images||[])].sort((a,b)=>({plate:0,opening:1}[a?.component]??2)-({plate:0,opening:1}[b?.component]??2));
  const nextMediaSignature=JSON.stringify([state.phase,review.videos,images,review.audio,review.plan,review.storyboard]);
  if(nextMediaSignature!==mediaSignature){mediaSignature=nextMediaSignature;media.replaceChildren();
  if(state.phase==='film'||state.phase==='complete'){for(const r of review.videos||[])asset(r,'video');}
  else if(state.phase==='audio'){asset(review.audio,'audio');for(const r of images)imageAsset(r);}
  else if(images.length&&state.phase!=='plan'){for(const r of images)imageAsset(r);}
  else{
   media.append(node('p','Review the production plan in the Storyboard section below.'));
  }
  }
  renderStoryboard(review);
  brief.replaceChildren();if(review.direction)brief.append(node('p',review.direction));
  if(['audio','film'].includes(state.phase)&&review.actionPlan?.length){brief.append(node('h3','Action'));for(const beat of review.actionPlan){brief.append(node('p',(beat.timing?beat.timing+' · ':'')+beat.action));}}
  for(const line of review.script||[]){const p=node('p');p.append(node('b',(line.speaker||'')+' '),node('em','“'+(line.exactText||line.text||line.words||'')+'”'));brief.append(p);}
  if(state.phase==='audio'&&review.performancePrompt){const p=node('details');p.append(node('summary','ElevenLabs performance prompt'),node('pre',review.performancePrompt));brief.append(p);}
  const decision=op?.status==='needs-decision'?op.decision:null;
  issue.replaceChildren();if(op?.status==='superseded'&&op.decision){issue.append(node('strong',op.decision.issue),node('p',op.decision.proposed));}if(decision){issue.append(node('strong',decision.issue),node('p',decision.proposed),node('p','Preserved: '+(decision.preserved||[]).join(', ')));}
  for(const concern of state.concerns||[]){issue.append(node('p',typeof concern==='string'?concern:concern.message||concern.observation||''));}
  cost.textContent=state.disclosure?.limitUsd?'Authorises '+(state.disclosure.operations||[]).join(', ')+' · up to $'+state.disclosure.limitUsd.toFixed(2)+'. '+(state.disclosure.basis||''):'No new generation cost.';
  const seePackage=review.seePackage||{}, montageMissing=review.storyboardRequired!==false&&!seePackage.providerSheet?.media;
  const imageRecords=Array.isArray(review.images)?review.images:[], plateApproved=imageRecords.some(item=>item?.component==='plate'&&item.reviewStatus==='approved'), openingApproved=imageRecords.some(item=>item?.component==='opening'&&item.reviewStatus==='approved');
  const montageIssues=Array.isArray(seePackage.issues)?seePackage.issues.filter(Boolean):[];
  const montageActionable=montageMissing&&options.storyboardGridAction&&!montageIssues.length&&plateApproved&&openingApproved;
  const montageBlock=!plateApproved?'Approve scene plate first':!openingApproved?'Approve opening keyframe first':montageIssues[0]?'Resolve SEE issue first':'';
  primary.textContent=state.busy?(op?.message||'Working…'):montageActionable?'Build storyboard montage':montageMissing?(montageBlock||'Prepare storyboard montage'):state.primary||'Waiting for the required decision';
  primary.hidden=state.phase==='complete';
  primary.disabled=state.busy||(!state.primary&&!decision)||submitted||(montageMissing&&!montageActionable);
  if(decision)primary.textContent='Check saved operation';
  changes.disabled=state.busy||!options.changes;
  evidenceBody.textContent=JSON.stringify({scope,state:state.phase,normalActions:state.normalActionCount,corrections:state.correctionActionCount,review,operation:op,qualification:'Software checks do not establish live visual compliance.'},null,2);
  const settledKey=op&&!state.busy?[op.id,op.status].join(':'):null;if(settledKey&&settledKey!==settledSignature){settledSignature=settledKey;options.settled?.(state);}
  if(previousPhase&&previousPhase!==state.phase&&state.phase==='film')options.phaseChanged?.(state.phase,previousPhase);
  if(awaitingNext&&state.phase==='complete'&&state.next&&options.next){awaitingNext=false;options.next(state.next);return;}
 }
 async function refresh(resume=false){clearTimeout(timer);if(ticket!==sequence||!host.isConnected)return;try{show(await api({command:resume?'resume':'status',scope}));if(state.busy)timer=setTimeout(()=>refresh(true),1800);}catch(e){issue.textContent=e.message;primary.disabled=true;}}
 primary.onclick=async()=>{if(!state||submitted||primary.disabled)return;const gridButton=host.querySelector('[data-storyboard-grid]');if(montageActionable&&gridButton&&!gridButton.disabled){gridButton.click();return;}submitted=true;if(state.operation?.status==='needs-decision'){try{show(await api({command:'recover',scope}));}catch(e){issue.textContent=e.message;}finally{submitted=false;refresh(true);}return;}awaitingNext=state.phase==='film';primary.disabled=true;progress.textContent='Starting '+state.primary+'…';try{show(await api({command:'decide',scope,action:state.phase,binding:state.binding,expectedRevision:state.revision,commandId:crypto.randomUUID(),by:options.reviewer||'Producer'}));}catch(e){issue.textContent=e.message;}finally{submitted=false;if(ticket===sequence)refresh(true);}};
 const handle=()=>{clearTimeout(timer);if(ticket===sequence)sequence++;};handle.scopeId=scopeId;handle.refresh=()=>refresh(true);host.journeyHandle=handle;refresh(true);return handle;
}
global.StudioJourney={mount};
})(window);
