"""Which refusals can a studio button actually return? Call-graph reachability from each
director action's entry function, plus every blocker code the studio can surface."""
import ast, io, os, re, json, collections

ROOT = r"C:\Users\julia\AiStudio"
ENGINE = os.path.join(ROOT, "engine")

def src(p): return io.open(p, encoding="utf-8", errors="replace").read()

# ---------- 1. index every engine function: its calls and its raises ----------
FUNCS = {}          # "module.func" -> {"calls": set(bare names), "raises": [(line, exc, msg)]}
BY_NAME = collections.defaultdict(list)   # bare name -> [qualnames]

def flat(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return flat(node.left) + flat(node.right)
    return "{}"

for fn in sorted(os.listdir(ENGINE)):
    if not fn.endswith(".py") or fn.startswith("test_"): continue
    mod = fn[:-3]
    try: tree = ast.parse(src(os.path.join(ENGINE, fn)))
    except SyntaxError: continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        qual = f"{mod}.{node.name}"
        calls, raises = set(), []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                f = n.func
                calls.add(getattr(f, "attr", None) or getattr(f, "id", None) or "")
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call):
                ename = getattr(n.exc.func, "attr", None) or getattr(n.exc.func, "id", None) or ""
                if re.search(r"Refused|Error$|Conflict", ename) and n.exc.args:
                    raises.append((n.lineno, ename, " ".join(flat(n.exc.args[0]).split())))
        FUNCS[qual] = {"calls": calls, "raises": raises, "mod": mod, "name": node.name}
        BY_NAME[node.name].append(qual)

print(f"indexed {len(FUNCS)} engine functions")

# ---------- 2. the studio's action -> engine entry points ----------
serve = src(os.path.join(ROOT, "cb-studio", "serve.py"))
action_ids = sorted(set(re.findall(r'"([a-z][a-z0-9-]+)"',
                    re.search(r"DIRECTOR_ACTION_IDS = \{(.*?)\}", serve, re.S).group(1))))
print(f"director actions: {len(action_ids)}")

# entry function per action, read from serve.py's dispatch + cb_studio_director helpers
ENTRY = {
    "direct-scene": ["cb_creative.run_scene"],
    "rebase-canon": ["cb_intake.rebase_canon_lock"],
    "build-scene-plate": ["cb_render.generate_scenelook_plate"],
    "select-scene-plate-library": ["cb_render.select_scenelook_source"],
    "select-scene-plate-upload": ["cb_render.select_scenelook_source"],
    "build-keyframe": ["cb_studio_director.build_keyframe", "cb_render.keyframe_shot"],
    "select-keyframe-library": ["cb_render.select_keyframe_source"],
    "select-keyframe-upload": ["cb_render.select_keyframe_source"],
    "select-keyframe-candidate": ["cb_render.select_keyframe_candidate"],
    "accept-keyframe": ["cb_render.approve_keyframe"],
    "iterate-keyframe": ["cb_render.reject_keyframe", "cb_studio_director.refire_keyframe"],
    "build-voice": ["cb_render.voice_shot"],
    "accept-voice": ["cb_render.approve_voice"],
    "iterate-voice": ["cb_render.reject_voice"],
    "prepare-render": ["cb_render.fire_shot"],
    "approve-spend": ["cb_render.fire_shot"],
    "cancel-spend": ["cb_render.cancel_spend_authorization"],
    "abandon-batch": ["cb_render.abandon_batch"],
    "override-model-limited": ["cb_render.override_model_limited"],
    "accept-animation": ["cb_render.approve_shot"],
    "iterate-animation": ["cb_render.reject_shot"],
    "reopen-shot": ["cb_render.reopen_approved_shot"],
    "run-ai-review": ["cb_render.prepare_department"],
    "run-quality-review": ["cb_render.prepare_department"],
    "accept-quality": ["cb_render.decide_department"],
    "build-master": ["cb_render.stitch_scene"],
    "run-final-review": ["cb_render.prepare_department"],
    "accept-master": ["cb_render.decide_department"],
    "iterate-master": ["cb_render.decide_department"],
    "save-retake-note": ["cb_render.save_watch_director_feedback"],
}

SKIP = {"str","int","float","bool","len","list","dict","set","sorted","print","open","getattr",
        "isinstance","json","append","get","format","join","strip","lower","upper","split","items",
        "keys","values","setdefault","update","pop","sub","match","search","exists","is_file",
        "read_text","write_text","mkdir","Path","round","abs","min","max","any","all","enumerate",
        "zip","range","sum","hexdigest","encode","decode","copy","replace","startswith","endswith"}

def reachable(entry, depth=6):
    """Refusals reachable from an entry function (bare-name call graph, bounded depth)."""
    seen, out, frontier = set(), [], [(entry, 0)]
    while frontier:
        qual, d = frontier.pop()
        if qual in seen or qual not in FUNCS or d > depth: continue
        seen.add(qual)
        info = FUNCS[qual]
        for line, exc, msg in info["raises"]:
            out.append({"at": f"{info['mod']}.py:{line}", "in": f"{info['mod']}.{info['name']}",
                        "exc": exc, "msg": msg, "depth": d})
        for name in info["calls"]:
            if not name or name in SKIP: continue
            for cand in BY_NAME.get(name, []):
                frontier.append((cand, d + 1))
    return out

results = {}
for action, entries in ENTRY.items():
    rows = []
    for e in entries:
        rows.extend(reachable(e))
    uniq = {}
    for r in rows:
        uniq.setdefault(r["at"], r)
    results[action] = sorted(uniq.values(), key=lambda r: (r["depth"], r["at"]))

print("\n=== refusals reachable per action (count) ===")
for a in sorted(results, key=lambda a: -len(results[a])):
    print(f"  {len(results[a]):4d}  {a}")

# ---------- 3. blocker codes the studio surfaces ----------
blockers = []
for rel in ("engine/cb_state.py", "engine/cb_production_preflight.py"):
    text = src(os.path.join(ROOT, rel))
    for m in re.finditer(r'"code":\s*"([A-Z_0-9]+)"(.*?)(?:\}\)|\},)', text, re.S):
        seg = m.group(2)
        msg = (re.search(r'"message":\s*\(?\s*"([^"]{0,160})', seg) or [None, ""])[1]
        act = (re.search(r'"action":\s*\(?\s*"([^"]{0,160})', seg) or [None, ""])[1]
        blockers.append({"file": rel, "code": m.group(1), "message": msg, "action": act})
    for m in re.finditer(r'block\(\s*"([A-Z_0-9]+)",\s*"[a-z-]+",\s*\(?\s*(?:f?")([^"]{0,160})', text):
        blockers.append({"file": rel, "code": m.group(1), "message": m.group(2), "action": ""})
seen = set(); dedup = []
for b in blockers:
    if b["code"] in seen: continue
    seen.add(b["code"]); dedup.append(b)
print(f"\n=== blocker codes: {len(dedup)} ===")
for b in sorted(dedup, key=lambda b: b["code"]):
    print(f"  {b['code']:34s} | {b['action'][:78] or b['message'][:78]}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reach.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(
    {"actions": results, "blockers": dedup}, indent=1, ensure_ascii=False))
print("\nwrote", out)
