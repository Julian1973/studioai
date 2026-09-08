"""Isolated browser-test server: real handlers and SQLite, synthetic media/providers.

Never use this server for production. Its workspace and credentials are temporary.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))


def main():
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='studio-review-browser-') as directory:
        temporary = Path(directory)
        os.environ['CB_STUDIO_SESSION_SECRET_FILE'] = str(temporary/'session.key')
        os.environ['CB_STUDIO_STATE_DB'] = str(temporary/'legacy.sqlite3')
        os.environ['CB_STUDIO_SKIP_PREWARM'] = '1'
        from test_studio_production import setup, FakeTransport
        from studio_editing import fields
        p, ws, old_transport, accounts = setup.__wrapped__(temporary)
        class Transport(FakeTransport):
            def direct(self, connection, key, model, system, context, *, planning=False, images=None):
                if not planning and context.get('selectedShot'):
                    new = fields(context['selectedShot'])
                    new['performance'] = 'Hesitate, take a small breath, then let relief arrive.'
                    self.reply = {'message':'Give the hesitation a clear breath while retaining voice and geography.', 'revisedShot':new}
                return super().direct(connection,key,model,system,context,planning=planning,images=images)
        p.transport=Transport()
        ws.save_services('first', {**ws.services('first'), 'review': {
            'connectionId': accounts['openai']['id'], 'model': 'test-vision', 'audioModel': 'test-audio', 'estimateUsd': .2}})
        for source in (ROOT/'cb-studio').iterdir():
            if source.suffix in {'.html','.css','.js'}:
                shutil.copyfile(source,ws.root/'cb-studio'/source.name)
        registry=ws.root/'cb-studio/data/projects.json'
        data=json.loads(registry.read_text())
        for meta in data['projects']:
            meta['episodesFile']=meta['configBase']+'/episodes.json'
            meta['name']='Harbour Lights' if meta['id']=='first' else 'Another World'
            meta['aspectRatio']='16:9';meta['theme']={'accent':'#a875ff'}
            (ws.root/meta['configBase']/'media-index.json').write_text('[]')
        registry.write_text(json.dumps(data))
        import studio_workspace, studio_production
        studio_workspace.Workspace=lambda root:ws
        studio_production.Production=lambda workspace:p
        spec=importlib.util.spec_from_file_location('studio_review_test_server',ROOT/'cb-studio/serve.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.ROOT=ws.root
        module.DATA=ws.root/'cb-studio/data'
        import requests
        requests.request=lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('External provider calls are disabled in this test server'))
        os.chdir(ws.root)
        with module.http.server.ThreadingHTTPServer(('127.0.0.1',0),module.H) as server:
            print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}/cb-studio/app.html#pg=projects','temporaryRoot':str(ws.root)}),flush=True)
            server.serve_forever()


if __name__=='__main__':main()
