import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('/Users/julianjenkins/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const server=spawn('/Users/julianjenkins/Desktop/Ai Studio/.venv/bin/python',['-u','journey_browser_server.py'],{cwd:new URL('.',import.meta.url),env:{...process.env,BROWSER_DEMO:'1',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:'/Users/julianjenkins/Desktop/Ai Studio/engine:/Users/julianjenkins/Desktop/Ai Studio/cb-studio'},stdio:['ignore','pipe','pipe']});
let browser;let errors='';server.stderr.on('data',d=>errors+=d);
try{
 const [data]=await once(server.stdout,'data');const {url}=JSON.parse(data.toString().trim().split('\n')[0]);
 browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--disable-background-networking','--disable-component-update','--no-first-run']});
 const context=await browser.newContext({viewport:{width:1300,height:1000}});
 await context.route('**/*',route=>route.request().url().startsWith(url+'/')?route.continue():route.abort());
 const page=await context.newPage();page.on('pageerror',e=>console.error('PAGE ERROR',e.message));page.on('console',m=>{if(m.type()==='error')console.error(m.text())});page.on('requestfailed',r=>console.error(r.url(),r.failure()));page.on('response',async r=>{if(r.status()===409)console.error('CONFLICT',r.url(),await r.text());if(r.url().includes('.mp4'))(r.status()>=400?console.error('MEDIA',r.url(),r.status()):null)});await page.goto(url);
 const labels=['Prepare Scene','Approve Plan & Create Images','Approve Images & Create Audio','Approve Audio & Render','Approve & Next'];
 const acted=[];const proofPrefix=process.env.PROJECT_DEMO?'project':'native';
 for(const label of labels){
  const button=page.getByRole('button',{name:label,exact:true});await button.waitFor().catch(async e=>{console.error(await page.locator('body').innerText());throw e;});await page.screenshot({path:fileURLToPath(new URL('journey-'+proofPrefix+'-'+(acted.length+1)+'.png',import.meta.url)),fullPage:true});if(label==='Approve & Next'){
   await page.locator('.journey-media video').evaluate(async v=>{v.muted=true;await v.play();});await page.waitForFunction(()=>document.querySelector('.journey-media video').currentTime>0);await page.locator('.journey-media video').evaluate(v=>v.pause());
  }await button.click();acted.push(label);
  await page.waitForFunction(()=>!document.querySelector('.journey-head p').textContent.startsWith('Starting'));
  if(label==='Approve Plan & Create Images'){await page.reload();}
 }
 if(process.env.PROJECT_SHELL){
  await page.locator('.journey-head').getByText(/S1.SH2/).waitFor();
  await page.locator('#sp-summary').getByText('1 / 2',{exact:true}).first().waitFor();
  const state=await page.evaluate(async()=>await(await fetch('/api/production-journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:{projectId:'first',episode:'1',scene:'1',unit:'S1.SH1'},command:'status'})})).json());
  assert.equal(state.normalActionCount,5);assert.equal(state.phase,'complete');
  await page.screenshot({path:fileURLToPath(new URL('five-action-project-shell-proof.png',import.meta.url)),fullPage:true});
 }else{
 await page.getByText('Accepted · ready for the next unit',{exact:true}).waitFor();
 await page.getByText('Direction, references and evidence',{exact:true}).click();
 const evidence=JSON.parse(await page.locator('details pre').first().textContent());
 assert.equal(evidence.normalActions,5);assert.equal(evidence.state,'complete');assert.equal(acted.length,5);
 await page.locator('video').evaluate(v=>new Promise((resolve,reject)=>{if(v.readyState>=1)return resolve();v.onloadedmetadata=resolve;v.onerror=()=>reject(new Error('Video failed to load'));setTimeout(()=>reject(new Error('Video load timeout')),5000);}));
 await page.locator('video').evaluate(async v=>{v.muted=true;await v.play();});await page.waitForFunction(()=>document.querySelector('video').currentTime>0);await page.locator('video').evaluate(v=>v.pause());
 await page.getByText('Direction, references and evidence',{exact:true}).click();
 await page.screenshot({path:fileURLToPath(new URL(process.env.PROJECT_DEMO?'five-action-project-browser-proof.png':'five-action-browser-proof.png',import.meta.url)),fullPage:true});

 }
 console.log(JSON.stringify({result:'PASS',normalActions:acted.length,actions:acted,reloadAfterImages:true,providers:'FAKE',externalNetwork:'blocked',liveStudio:'not contacted'}));
}catch(error){console.error(errors);throw error;}finally{await browser?.close();server.kill('SIGTERM');}
