import assert from 'node:assert/strict';
import {readFile, mkdir} from 'node:fs/promises';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('/Users/julianjenkins/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const js=await readFile(new URL('journey.js',import.meta.url),'utf8');
const css=await readFile(new URL('journey.css',import.meta.url),'utf8');
const requests=[],errors=[];
const pixel=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII=','base64');
const picture=process.env.STUDIO_TEST_IMAGE?await readFile(process.env.STUDIO_TEST_IMAGE):pixel;
const baseView={phase:'images',primary:'Approve SEE & Create Audio',revision:1,binding:'first',busy:false,
 disclosure:{limitUsd:12,operations:['voice']},review:{images:[
 {component:'plate',label:'Scene plate',url:'/plate.png',reviewStatus:'pending'},
 {component:'opening',label:'Opening keyframe',url:'/opening.png',reviewStatus:'approved'}],
 storyboard:[{viewId:'S3-V01',action:'Sunny places the cup.',camera:'Low close view'}],
 storyboardRequired:true,seePackage:{binding:'see-v1',panels:[],issues:[],providerSheet:{}},
 references:{keyframe:{references:[{role:'Sunny',status:'missing',message:'Sunny identity reference is missing'}]},animation:{references:[{role:'scene plate',status:'ready',url:'/plate.png'}]}}}};
let view=structuredClone(baseView);
const server=createServer(async(req,res)=>{
 if(req.url==='/api/production-journey'){
  let body='';for await(const part of req)body+=part;
  const data=JSON.parse(body);requests.push(data);
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(view));return;
 }
 if(req.url.endsWith('.png')){res.setHeader('Content-Type','image/png');res.end(picture);return;}
 res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:20px;background:#101116;color:#eee;font:14px Arial;--surface:#181921;--surface2:#20212b;--muted:#adb0bf;--line:#393b49;--brand:#80618b}button{font:inherit;min-height:36px;padding:8px 12px;border:1px solid #444652;border-radius:4px;background:#745679;color:white;cursor:pointer}button:disabled{opacity:.5}button.ghost{background:#252632}figure img{max-width:100%}${css}</style><main id="workspace"></main><script>${js}</script>`);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
let browser,page;
try{
 browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 page=await browser.newPage({viewport:{width:1280,height:960}});
 page.setDefaultTimeout(8000);
 await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);
 await page.evaluate(()=>{
  window.calls=[];
  window.options={reviewer:'Julian',changes:()=>calls.push({direct:true}),openHear:()=>calls.push({hear:true}),
   openStage:stage=>calls.push({stage}),openLibrary:()=>calls.push({library:true}),
   imageSourceAction:async d=>{calls.push({source:d.action,component:d.component});},
   imageAction:async d=>{calls.push({review:d.action});throw new Error('Current approval could not be saved');},
   storyboardAction:async d=>calls.push({required:d.required}),
   storyboardPanelAction:async d=>calls.push({panel:d.command}),
   storyboardGridAction:async()=>calls.push({grid:true})};
  window.scope={projectId:'crystal-bears',episode:'Ep4',scene:'3',unit:'S3.SH1'};
  StudioJourney.mount(document.querySelector('main'),scope,options);
 });
 const primary=page.locator('.journey-actions>.btn').first();
 const decide=async command=>{
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/production-journey')&&r.request().postDataJSON()?.command===command),primary.click()]);
  await page.waitForFunction(()=>!document.querySelector('.journey-actions>.btn').disabled);
 };
 const refresh=async next=>{view=structuredClone(next);await page.evaluate(()=>document.querySelector('main').journeyHandle.refresh());};
 await page.getByRole('button',{name:'Approve Scene plate',exact:true}).waitFor();
 assert.equal(await primary.isDisabled(),true);
 assert.equal(await page.locator('img[alt^="Visual storyboard panel"]').count(),0,'Planning references must not impersonate generated panels');
 assert.equal(await page.getByText(/SEE references used for creation/).count(),1);
 assert.equal(await page.getByText('keyframe · Sunny · Sunny identity reference is missing',{exact:true}).count(),1);
 const plate=page.locator('.journey-image-card').first();
 await plate.getByRole('button',{name:'Library',exact:true}).click();
 assert.equal(await plate.getByRole('button',{name:'Library',exact:true}).isEnabled(),true);
 await plate.getByRole('button',{name:'Refire',exact:true}).click();
 assert.equal(await plate.getByRole('button',{name:'Refire',exact:true}).isEnabled(),true);
 await plate.locator('input[type=file]').setInputFiles({name:'plate.png',mimeType:'image/png',buffer:pixel});
 assert.deepEqual(await page.evaluate(()=>calls.filter(c=>c.source).map(c=>c.source)),['library','refire','upload']);
 await plate.getByRole('button',{name:'Approve Scene plate',exact:true}).click();
 await page.getByText('Current approval could not be saved',{exact:true}).waitFor();
 assert.equal(await plate.getByRole('button',{name:'Approve Scene plate',exact:true}).isEnabled(),true);
 assert.equal(await page.getByRole('button',{name:'Approve Opening keyframe',exact:true}).isDisabled(),true);

 await refresh({...baseView,phase:'prepare',primary:'Prepare Scene',review:{}});
 await decide('decide');
 assert.equal(requests.filter(r=>r.command==='decide').at(-1).action,'prepare');
 await refresh({...baseView,phase:'plan',primary:'Approve DIRECT & Open SEE'});
 assert.equal(await primary.isEnabled(),true,'Montage must not block DIRECT');
 await refresh({...baseView,review:{...baseView.review,images:[]}});
 assert.equal(await page.locator('.journey-image-card').count(),2,'Missing image must keep source controls');

 const approved=baseView.review.images.map(r=>({...r,reviewStatus:'approved'}));
 const panel={id:'p1',viewId:'S3-V01',action:'Cup aligned',status:'current',reviewStatus:'approved',media:{url:'/panel.png'},reuseOpening:true};
 await refresh({...baseView,review:{...baseView.review,images:approved,seePackage:{binding:'see2',panels:[panel],providerSheet:{status:'stale',media:{url:'/old-montage.png'}},issues:[]}}});
 assert.equal(await page.locator('.journey-storyboard-grid img').count(),0,'Do not display stale montage as current');
 await primary.click();
 assert.equal(await page.evaluate(()=>calls.filter(c=>c.grid).length),1);
 const skipped={...baseView,review:{...baseView.review,images:approved,storyboardRequired:false,storyboardChoice:{required:false}}};
 await refresh(skipped);
 assert.equal(await primary.isEnabled(),true,'Optional storyboard must not block continuation');

 await refresh({...skipped,phase:'audio',primary:'Approve Audio & Render',creativeReview:{canApprove:true,approveLabel:'Approve audio'}});
 await decide('decide');
 assert.equal(requests.filter(r=>r.command==='decide').at(-1).intent,'approve','Audio approval cannot authorize rendering');
 assert.equal(await page.locator('.journey-cost').innerText(),'No new generation cost.');
 await refresh({...baseView,operation:{id:'failed',status:'needs-decision',decision:{issue:'Input changed',proposed:'Review current input'}}});
 assert.equal(await primary.isEnabled(),true,'Recovery must stay reachable with missing storyboard');
 await decide('recover');assert.equal(requests.some(r=>r.command==='recover'),true);

 await refresh({...baseView,operation:{id:'review-failed',status:'needs-decision',grant:{limitUsd:2.5},
  decision:{issue:'WATCH_PROMPT_REVIEW_REQUIRED',proposed:'Retry review',
   producer:{category:'direction',headline:'Review could not verify its evidence.',meaning:'Approved work is retained.',nextAction:'Retry or review direction.',button:'Retry review',preserved:'Everything approved is saved.'}}}});
 assert.match(await page.locator('.journey-cost').innerText(),/original action cap of \$2\.50/);
 assert.equal(await page.getByRole('button',{name:'Review in DIRECT',exact:true}).count(),1);
 await page.getByRole('button',{name:'Review in DIRECT',exact:true}).click();
 assert.equal(await page.evaluate(()=>calls.some(c=>c.stage==='direct'||c.direct)),true,'Producer can choose manual direction review');
 await refresh({...baseView,phase:'audio',operation:{id:'audio-failed',status:'needs-decision',grant:{limitUsd:0},
  decision:{issue:'Audio needs review',proposed:'Open HEAR',
   producer:{category:'audio',headline:'Audio needs review.',meaning:'Approved work is retained.',nextAction:'Open HEAR.',button:'Retry',preserved:'Everything approved is saved.'}}}});
 assert.equal(await page.getByRole('button',{name:'Open HEAR',exact:true}).count(),1);
 await page.getByRole('button',{name:'Open HEAR',exact:true}).click();
 assert.equal(await page.evaluate(()=>calls.some(c=>c.hear)),true,'Producer can choose HEAR without retrying generation');
 await refresh({...baseView,phase:'audio',operation:{id:'direct-fix',status:'needs-decision',
  decision:{issue:'Voice direction is missing',proposed:'Review DIRECT',producer:{category:'audio',targetStage:'direct',headline:'Voice direction needs attention.',meaning:'Approved work is retained.',nextAction:'Add acting direction in DIRECT.',button:'Open direction',preserved:'Everything approved is saved.'}}}});
 await page.evaluate(()=>{window.calls.length=0;});
 const recoverCountBeforeDirect=requests.filter(r=>r.command==='recover').length;
 await primary.click();
 assert.deepEqual(await page.evaluate(()=>calls.filter(c=>c.stage).map(c=>c.stage)),['direct'],'Top action opens the named repair stage');
 assert.equal(requests.filter(r=>r.command==='recover').length,recoverCountBeforeDirect,'Navigation does not resume or rerun a failed operation');

 await page.evaluate(()=>{window.calls.length=0;});
 await refresh({...baseView,phase:'film',operation:{id:'provider-timeout',status:'needs-decision',
  decision:{issue:'APITimeoutError: Request timed out.',proposed:'Check whether the provider accepted the request.',
   producer:{category:'provider',headline:'The provider did not answer in time.',meaning:'The job may already exist.',nextAction:'Check the existing job before retrying.',button:'Check existing job',preserved:'Everything approved is saved.'}}}});
 const providerRecoverCount=requests.filter(r=>r.command==='recover').length;
 await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/production-journey')&&r.request().postDataJSON()?.command==='recover'),primary.click()]);
 assert.equal(requests.filter(r=>r.command==='recover').length,providerRecoverCount+1,'Timeout recovery checks the saved operation instead of routing to DIRECT or resubmitting');
 assert.deepEqual(await page.evaluate(()=>calls),[],'Timeout recovery does not navigate to an unrelated stage');

 await refresh({...skipped,phase:'audio',busy:true,operation:{id:'watch',status:'running',requestDisplayHash:'sealed',receipts:{prepare_render:{requestDisplay:{prompt:'Exact sealed prompt',maximumUsd:2}}}}});
 await page.getByText('WATCH · Final request',{exact:true}).waitFor();
 await decide('request-displayed');
 assert.deepEqual(requests.find(r=>r.command==='request-displayed'),{command:'request-displayed',scope:{projectId:'crystal-bears',episode:'Ep4',scene:'3',unit:'S3.SH1'},operationId:'watch',requestHash:'sealed'});
 await refresh({...skipped,phase:'film',primary:'Approve & Next',creativeReview:{canApprove:true},review:{...skipped.review,videos:[]}});
 await decide('decide');assert.equal(requests.filter(r=>r.command==='decide').at(-1).action,'film');

 await page.evaluate(()=>{const host=document.querySelector('main');host.replaceChildren();StudioJourney.mount(host,scope,options);});
 await page.locator('.journey-head').waitFor();
 await refresh({...baseView,review:{...baseView.review,images:approved,seePackage:{panels:[panel],providerSheet:{status:'current',media:{url:'/montage.png'}},issues:[]}}});
 const out=process.env.STUDIO_TEST_OUTPUT||'/private/tmp/studio-workflow-proof';await mkdir(out,{recursive:true});
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:960});
  await page.screenshot({path:`${out}/journey-${width}.png`,fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}px`);
  for(const button of await page.locator('.journey-image-source-actions button').all()){
   assert.equal(await button.evaluate(el=>el.scrollWidth<=el.clientWidth),true,'Button label overflow');
  }
 }
 // SEE before the plate exists: the unit is still in 'plan' and the recorded stop asks for
 // the scene plate. The producer must see the two SEE tiles (plate, then keyframe) with
 // their Upload / Refire / Library controls, and the stop's button must open the plate
 // library on this surface instead of re-running the failed step.
 await page.setViewportSize({width:1280,height:960});
 await page.evaluate(()=>{window.calls.length=0;});
 await refresh({phase:'plan',primary:'',revision:9,binding:'plan-1',busy:false,
  operation:{id:'op-plate',status:'needs-decision',decision:{issue:'REFUSED — no current signed scene plate found for Ep4 scene 3',proposed:'Choose or generate the scene plate.',
   producer:{category:'images',headline:"The scene's background plate needs approving first.",meaning:'Every scene is anchored on one approved world plate before its first image.',nextAction:'Choose the plate from your library, upload one, or generate one, then approve it and continue.',button:'Open scene plate',preserved:'Everything you approved is saved.'}}},
  review:{images:[],plate:null,storyboard:baseView.review.storyboard,storyboardRequired:false,seePackage:{binding:'see-plan',panels:[],issues:[],providerSheet:{}}}});
 const tiles=page.locator('.journey-image-card');
 await tiles.first().waitFor();
 assert.equal(await tiles.count(),2,'SEE shows the scene plate and the opening keyframe tiles before either exists');
 assert.deepEqual(await tiles.evaluateAll(cards=>cards.map(c=>c.dataset.component)),['plate','opening'],'Scene plate first, keyframe second');
 assert.equal(await page.getByText('Review the production plan in the Storyboard section below.').count(),0,'No text wall in place of the SEE tiles');
 assert.equal(await page.getByRole('button',{name:'Library',exact:true}).count(),2,'Each tile offers the library');
 assert.equal(await primary.textContent(),'Open scene plate');
 const recoversBefore=requests.filter(r=>r.command==='recover').length;
 await primary.click();
 await page.waitForFunction(()=>window.calls.some(c=>c.source==='library'&&c.component==='plate'));
 assert.equal(requests.filter(r=>r.command==='recover').length,recoversBefore,'The plate stop never re-runs the failed step');
 await refresh({phase:'audio',primary:'',revision:10,binding:'see-stale',busy:false,
  operation:{id:'op-opening-stale',status:'needs-decision',decision:{issue:'REFUSED — opening-frame approval is stale against its direct inputs',proposed:'Review the updated opening frame.',
   producer:{category:'images',targetStage:'see',component:'opening',headline:'The opening frame needs updating.',meaning:'Its inputs changed; the saved image is retained.',nextAction:'Review the opening frame in SEE.',button:'Review opening frame',preserved:'Everything you approved is saved.'}}},
  review:{...baseView.review,images:[{component:'plate',label:'Scene plate',url:'/plate.png',reviewStatus:'approved'},
   {component:'opening',label:'Opening keyframe',url:'/opening.png',reviewStatus:'stale'}],storyboardRequired:false,seePackage:{binding:'see-stale',panels:[],issues:[],providerSheet:{}}}});
 const openingActionCount=requests.filter(r=>r.command==='recover').length;
 await primary.click();
 await page.waitForFunction(()=>window.calls.some(c=>c.source==='library'&&c.component==='opening'));
 assert.equal(requests.filter(r=>r.command==='recover').length,openingActionCount,'Stale opening recovery never routes through the plate or blind retry');
 assert.deepEqual(errors,[]);
 console.log('PASS: SEE tiles before the plate exists, source controls, missing assets, approval failure, DIRECT, optional storyboard, real montage, HEAR approval, recovery, sealed WATCH, REVIEW, remount, desktop/mobile. External requests blocked.');
}catch(error){console.error(error,errors,await page?.locator('body').innerText());throw error;}
finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
