"""Disposable real-route browser fixture. Never attaches to the live Studio."""
import tempfile
from pathlib import Path
import sys,json,shutil,threading,os
from pytest import MonkeyPatch
from test_journey_http import fixture
root=Path(tempfile.mkdtemp(prefix='studio-journey-browser-'))
mp=MonkeyPatch()
if os.environ.get('PROJECT_DEMO'):
    from test_journey_acceptance import live_controls,SCOPE
    from test_studio_production import setup
    fixture_data=setup.__wrapped__(root)
    server,ws,transport,_=live_controls.__wrapped__(fixture_data,mp)
    root=ws.root;scope=SCOPE
    import studio_workspace
    mp.setattr(studio_workspace,'Workspace',lambda *a,**k:ws)
else:
    server,setup,calls=fixture.__wrapped__(root,mp)
    scope,_,_=setup(1)
static=root/'cb-studio';static.mkdir(exist_ok=True)
for file in ('journey.js','journey.css','project-production.js','project-production.css','project-review.js'):
    shutil.copyfile(Path(__file__).with_name(file),static/file)
page='''<!doctype html><html><head><meta charset="utf-8"><title>Studio journey — offline fixture</title><link rel="stylesheet" href="/cb-studio/journey.css"><style>body{background:#13141b;color:#eee;font:16px system-ui;margin:30px;--muted:#aaa;--surface:#20222b;--surface2:#252834;--line:#424551;--brand:#9d82b4}.btn{padding:16px;border-radius:6px;background:#b094c5;color:#121318;border:0;font:inherit;cursor:pointer}.btn:disabled{opacity:.5}</style></head><body><main id="workspace"></main><script src="/cb-studio/journey.js"></script><script>StudioJourney.mount(document.getElementById('workspace'),SCOPE,{changes:()=>{}})</script></body></html>'''.replace('SCOPE',json.dumps(scope))
if os.environ.get('PROJECT_SHELL'):
    page=page.replace('<main id="workspace"></main>', '<main id="projectProduction"></main>')
    page=page.replace('<script src="/cb-studio/journey.js"></script>', '<script>const BASE=""; const CURRENT_PROJECT={id:"first",name:"First",setupVersion:1};</script><link rel="stylesheet" href="/cb-studio/project-production.css"><script src="/cb-studio/journey.js"></script><script src="/cb-studio/project-production.js"></script><script src="/cb-studio/project-review.js"></script>')
    page=page.replace("StudioJourney.mount(document.getElementById('workspace'),"+json.dumps(scope)+",{changes:()=>{}})", 'StudioProduction.mount(CURRENT_PROJECT,[{number:1,title:"Opening"}])')
# Test fixture GET returns real component assets; POST remains actual Studio H.
original=server.H.do_GET
from urllib.parse import urlsplit

def get(self):
    path=urlsplit(self.path).path
    if path.startswith(('/engine/media/shots/','/projects/')):
        asset=(root/path.lstrip('/')).resolve()
        if asset.is_file() and asset.is_relative_to(root.resolve()) and asset.suffix in {'.mp4','.wav','.png','.jpg','.jpeg'}:
            data=asset.read_bytes();self.send_response(200);self.send_header('Content-Type','video/mp4' if path.endswith('.mp4') else 'audio/wav' if path.endswith('.wav') else 'image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
    if path=='/' or (path.startswith('/cb-studio/') and Path(path).name in ('journey.js','journey.css','project-production.js','project-production.css','project-review.js')):
        data=page.encode() if path=='/' else (static/Path(path).name).read_bytes()
        self.send_response(200);self.send_header('Content-Type','text/html' if path=='/' else 'text/javascript' if path.endswith('.js') else 'text/css');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
    return original(self)
server.H.do_GET=get
httpd=server.http.server.ThreadingHTTPServer(('127.0.0.1',0),server.H)
print(json.dumps({'url':f'http://127.0.0.1:{httpd.server_port}'}),flush=True)
try:httpd.serve_forever()
finally:httpd.server_close();mp.undo();shutil.rmtree(root)
