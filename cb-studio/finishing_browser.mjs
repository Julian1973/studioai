#!/usr/bin/env node
// Real finishing UI and playable synthetic media; isolated API fixture, no production writes.
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('playwright');
const media=execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=30','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-movflags','frag_keyframe+empty_moov','-f','mp4','pipe:1']);
const candidate=hash=>({available:true,masterSha256:hash,masterUrl:'/review.mp4',durationSec:3,status:'review-required',
  finishingWorkflow:{version:hash,drive:{verified:false},findings:[]},
  upscale:{settings:'Test only',missing:['not configured'],canStart:false,job:{runId:'fixture',status:'processing'}}});
let current=candidate('cut-a'),calls=[],pendingDecision;
const server=createServer(async(req,res)=>{
  try{
    const pathname=new URL(req.url,'http://localhost').pathname;
    if(req.method==='POST'){
      let raw='';for await(const chunk of req)raw+=chunk;
      const data=JSON.parse(raw);calls.push(data);let value;
      if(pathname==='/api/post-workspace'){
        await new Promise(resolve=>{pendingDecision=resolve;});
        current.verdict={verdict:'rejected',note:data.note};value=current;
      }else if(data.action==='resolve')value={product:'Resolve',version:'test',project:'Other film',timeline:'Other cut',startFrame:0,endFrame:90,frameRate:30,
        binding:{status:'mismatch',message:'Resolve is showing a different project or timeline.'}};
      else if(data.action==='director-brief')value={instruction:'Inspect the supplied cut.',dimensions:[],directorContract:'Project direction',postSupervisorContract:'Post review',postSupervisorReferences:{}};
      else value=current;
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify(value));return;
    }
    if(pathname==='/review.mp4'){res.setHeader('Content-Type','video/mp4');res.end(media);return;}
    const file=pathname.split('/').pop();
    if(!['finishing.html','finishing.js','project-drafts.js'].includes(file)){res.writeHead(404);res.end();return;}
    res.setHeader('Content-Type',file.endsWith('.html')?'text/html':'text/javascript');
    res.end(await readFile(new URL(file,import.meta.url)));
  }catch(error){res.writeHead(500);res.end(JSON.stringify({error:error.message}));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1280,height:960}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/finishing.html?episode=Ep2`);
  await page.locator('#note').fill('Keep this unsent repair note');
  await page.reload();await page.locator('#note').waitFor();
  assert.equal(await page.locator('#note').inputValue(),'Keep this unsent repair note');
  await page.locator('#resolve').click();await page.getByText(/Candidate binding: mismatch/).waitFor();
  await page.locator('#brief').click();await page.getByText(/does not claim a completed visual review/).waitFor();
  assert.equal(await page.locator('#approve').isDisabled(),true);
  current.finishingWorkflow.drive={verified:true,masterSha256:'older-cut'};
  await page.reload();await page.locator('#approve').waitFor();
  assert.equal(await page.locator('#approve').isDisabled(),true,'An older receipt must not enable approval');
  current.finishingWorkflow.drive.masterSha256='cut-a';
  await page.reload();await page.locator('#approve').waitFor();
  assert.equal(await page.locator('#approve').isEnabled(),true);
  await page.waitForFunction(()=>document.querySelector('video').readyState>=1);
  await page.locator('video').evaluate(async video=>{video.muted=true;await video.play();});
  await page.waitForFunction(()=>document.querySelector('video').currentTime>=1);
  await page.locator('video').evaluate(video=>{video.pause();video.dataset.identity='retained';});
  const refreshed=page.waitForResponse(response=>response.request().postDataJSON()?.action==='status');
  await page.locator('#poll').click();await refreshed;
  await page.waitForFunction(()=>document.querySelector('video').dataset.identity==='retained');
  assert.equal(await page.locator('#note').inputValue(),'Keep this unsent repair note');
  assert.ok((await page.locator('video').evaluate(v=>v.currentTime))>=.9);
  current=candidate('cut-b');await page.reload();await page.locator('#note').waitFor();
  assert.equal(await page.locator('#note').inputValue(),'','Notes must not transfer to a replacement cut');
  current=candidate('cut-a');await page.reload();await page.locator('#note').waitFor();
  assert.equal(await page.locator('#note').inputValue(),'Keep this unsent repair note');
  await page.locator('#reject').click();
  await page.waitForFunction(()=>document.querySelector('#note')!==null);
  // Wait for the submitted request to reach the fixture without using a fixed delay.
  const deadline=Date.now()+5000;
  while(!pendingDecision&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,10));
  assert.ok(pendingDecision,'Review decision reaches the server');
  await page.locator('#note').fill('A newer note typed while saving');pendingDecision();
  await page.getByText('Returned for repairs. Your notes are saved.',{exact:true}).waitFor();
  assert.equal(await page.locator('#note').inputValue(),'A newer note typed while saving');
  assert.equal(current.verdict.note,'Keep this unsent repair note');
  assert.ok(calls.every(call=>call.projectId==='crystal-bears'));
  assert.ok(!calls.some(call=>['approve','upscale'].includes(call.action)));
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'/tmp/studio-resolve-finishing-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: candidate-scoped draft recovery, timeline mismatch, brief-only status, approval gate, playback and notes across refresh, typing during save, mobile layout. No production writes or provider calls.');
}finally{if(browser)await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
