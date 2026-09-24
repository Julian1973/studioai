"""Exercise the real failure-copy function without browser or provider traffic."""
import json
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("error,title", [
    ("immutable script content is missing", "Production source files need recovery"),
    ("REFUSED — production handover is stale: script-version-mismatch", "Production handover needs attention"),
    ("REFUSED — S3.SH1 has no typed opening-frame layout", "Opening-frame direction needs attention"),
    ("DIRECT_REVISION_REQUIRED: Director Card is incomplete", "DIRECT needs review"),
    ("REFUSED — S3.SH1 has no current Director Review approval", "Film review required before assembly"),
    ("direction is stale", "Direction needs refreshing"),
    ("unknown failure", "Studio could not complete this step"),
])
def test_failure_explains_blocker_without_promising_automatic_repair(error, title):
    source = Path(__file__).with_name("app.html").read_text()
    function = source[source.index("function shFailureCopy(j){"):source.index("function shIsSpendDecision(j){")]
    script = function + "\nconsole.log(JSON.stringify(shFailureCopy(" + json.dumps({"log": error}) + ")));"
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    copy = json.loads(result.stdout)
    assert copy["title"] == title
    assert "will rebuild" not in copy["detail"]
    assert "only if the same step fails again" not in copy["detail"]


def test_error_details_survive_polling_and_copy_full_log():
    source = Path(__file__).with_name("app.html").read_text()
    functions = source[source.index("function shFailureCopy(j){"):source.index("function closeM(){")]
    banner = source[source.index("function renderJobBanner(){"):source.index("// ── Scene contents")]
    script = r'''
const assert=require('node:assert/strict');
const _esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;');
const _attr=s=>_esc(s).replaceAll('"','&quot;');
const copyErrorButton=text=>`<button data-error-copy="${_attr(text)}">Copy error</button>`;
const isSupersededWatchFailure=()=>false;
let writes=0, html='';
const el={get innerHTML(){return html},set innerHTML(s){html=s;writes++},
querySelector(){return html.includes('data-job-error')?{}:null}};
const document={getElementById:id=>id==='jobbanner'?el:null};
const localStorage={getItem:()=>null};
const page='pipeline',SH_SC=3,SH_EP='Ep4',jobFor=()=>null;
let SH_LAST_JOB={id:'error-1',episode:'Ep4',scene:3,status:'failed',log:'FIRST ERROR\n'+Array(30).fill('detail').join('\n')+'\n<last>'};
'''+functions+banner+r'''
renderJobBanner();
assert.equal(writes,1);
assert.ok(html.includes('Copy error'));
assert.ok(html.includes('FIRST ERROR'));
assert.ok(html.includes('&lt;last>'));
const key=JSON.stringify(['Ep4',3,'error-1']);
shRememberErrorDetails({isConnected:true,dataset:{jobError:key},open:true});
renderJobBanner();renderJobBanner();
assert.equal(writes,1,'polling must preserve the actual DOM and selection');
assert.match(shJobHTML(SH_LAST_JOB),/open ontoggle/);
shRememberErrorDetails({isConnected:false,dataset:{jobError:key},open:false});
assert.match(shJobHTML(SH_LAST_JOB),/open ontoggle/);
assert.doesNotMatch(shJobHTML({...SH_LAST_JOB,id:'error-2'}),/open ontoggle/);
shRememberErrorDetails({isConnected:true,dataset:{jobError:key},open:false});
assert.doesNotMatch(shJobHTML(SH_LAST_JOB),/open ontoggle/);
'''
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
