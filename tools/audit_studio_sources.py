"""Read-only audit of active source, worker references, docs and executable skill boundaries."""
import argparse
from collections import Counter
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT):
    root = Path(root)
    python_files = sorted(p for area in ('engine','cb-studio','tools') for p in (root/area).glob('*.py'))
    modules = {p.stem for p in python_files}
    issues, references = [], []
    for path in python_files:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        if path.name.startswith('test_'):
            continue
        counts=Counter(n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)))
        for name,count in counts.items():
            if count>1:issues.append({'kind':'shadowed-definition','file':str(path.relative_to(root)),'name':name})
        for node in ast.walk(tree):
            names = [a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else (
                [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
            for name in names:
                if name.startswith('cb_'):
                    item = {'file':str(path.relative_to(root)), 'line':node.lineno, 'module':name}
                    references.append(item)
                    if name not in modules:issues.append({'kind':'missing-local-import',**item})
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.fullmatch(r'cb_[a-z0-9_]+\.py',node.value):
                if not (root/'engine'/node.value).is_file():
                    issues.append({'kind':'missing-worker','file':str(path.relative_to(root)), 'line':node.lineno,'worker':node.value})
    docs = sorted([*root.glob('*.md'),*(root/'docs').glob('*.md'),*(root/'cb-studio').glob('*.md'),*(root/'skills').rglob('*.md')])
    for path in docs:
        text=path.read_text(encoding='utf-8')
        if '\0' in text:issues.append({'kind':'nul-in-document','file':str(path.relative_to(root))})
        # Inline Markdown links only; code examples and historical canon are not runtime file declarations.
        for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^)]+)\)', text):
            target=match.group(1).strip('<>').split('#')[0]
            if not target or re.match(r'[a-z]+:|^/',target):continue
            if not (path.parent/unquote(target)).exists():
                issues.append({'kind':'broken-doc-link','file':str(path.relative_to(root)),'target':target})
    browser_routes = {}
    server=root/'cb-studio/serve.py'
    if server.is_file():
        routes={node.value.split('?')[0] for node in ast.walk(ast.parse(server.read_text()))
                if isinstance(node,ast.Constant) and isinstance(node.value,str)
                and node.value.startswith('/api/') and '\n' not in node.value}
        for name in ('app.html','director.js','room.html','board.html'):
            path=root/'cb-studio'/name
            if not path.exists():continue
            used=set(re.findall(r'/api/[a-zA-Z0-9_/-]+',path.read_text()))
            browser_routes[name]=len(used)
            for route in used-routes:issues.append({'kind':'undeclared-browser-route','file':str(path.relative_to(root)),'route':route})
    skill_records=[]
    for path in (root/'skills').glob('*/SKILL.md'):
        text=path.read_text();start='<!-- RUNTIME_WORKER_START -->';end='<!-- RUNTIME_WORKER_END -->'
        if start in text:
            if text.count(start)!=1 or text.count(end)!=1:issues.append({'kind':'invalid-runtime-boundary','file':str(path.relative_to(root))})
            else:
                role=text.split(start)[1].split(end)[0]
                skill_records.append({'path':str(path.relative_to(root)),'runtimeSha256':hashlib.sha256(role.encode()).hexdigest(),'bytes':path.stat().st_size})
    return {'scope':'Top-level engine, server and maintenance Python; current Markdown and marked runtime skills. Excludes generated state/media, historical archives, locked canon prose, vendored grammar and unrelated imported projects.',
            'pythonFilesParsed':len(python_files),'documentsChecked':len(docs),'localImportReferences':len(references),
            'browserRouteCounts':browser_routes,'runtimeSkills':skill_records,'issues':issues,'ready':not issues,
            'retainedCompatibility':['director.html advanced inspector','legacy lock metadata readers','locked Studio Bible provenance; not supplied as workflow instructions']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=audit();path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('pythonFilesParsed','documentsChecked','issues','ready')}))
    raise SystemExit(0 if result['ready'] else 1)
