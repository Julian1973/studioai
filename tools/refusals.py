"""Enumerate every refusal the engine can raise and every blocker the studio can surface."""
import ast, io, os, re, json, collections

ROOT = r"C:\Users\julia\AiStudio"
ENGINE = os.path.join(ROOT, "engine")

def src(p): return io.open(p, encoding="utf-8", errors="replace").read()

def flatten(node):
    """Best-effort literal text of a string/f-string/concat expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
            else:
                out.append("{}")
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return flatten(node.left) + flatten(node.right)
    if isinstance(node, ast.Call):
        f = node.func
        name = getattr(f, "attr", None) or getattr(f, "id", None)
        if name == "join" and node.args:
            return flatten(f.value) + "{}" if isinstance(f, ast.Attribute) else "{}"
        return "{}"
    return "{}"

def enclosing_funcs(tree):
    spans = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((n.lineno, getattr(n, "end_lineno", n.lineno), n.name))
    spans.sort(key=lambda s: (s[0], -s[1]))
    def owner(line):
        best = None
        for a, b, name in spans:
            if a <= line <= b and (best is None or a >= best[0]):
                best = (a, name)
        return best[1] if best else "<module>"
    return owner

rows = []
for fn in sorted(os.listdir(ENGINE)):
    if not fn.endswith(".py") or fn.startswith("test_"):
        continue
    path = os.path.join(ENGINE, fn)
    text = src(path)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    owner = enclosing_funcs(tree)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Raise) or n.exc is None:
            continue
        exc = n.exc
        if not isinstance(exc, ast.Call):
            continue
        ename = getattr(exc.func, "attr", None) or getattr(exc.func, "id", None) or ""
        if not re.search(r"Refused|Error$|Conflict|Exit", ename):
            continue
        msg = flatten(exc.args[0]) if exc.args else ""
        rows.append({"file": fn, "line": n.lineno, "func": owner(n.lineno),
                     "exc": ename, "msg": " ".join(msg.split())})

print(f"TOTAL raise sites: {len(rows)}")
by_exc = collections.Counter(r["exc"] for r in rows)
print("BY EXCEPTION:", dict(by_exc.most_common()))
by_file = collections.Counter(r["file"] for r in rows)
print("BY FILE:", dict(by_file.most_common(18)))

# Family classification by message keywords - the audit's own grouping.
FAMILIES = [
    ("canon-incomplete",   r"locked identity pack|identity reference|not production-ready|CANON LOCK REFUSED|not in the locked roster|canon-lock|canon snapshot"),
    ("direction-stale",    r"direction is stale|Prepare current .* direction|specialist direction|direction is missing|contract-invalid|animation-compiler-output-stale"),
    ("approval-stale",     r"stale against|no longer match|superseded|not current|approval is stale|does not match current"),
    ("approval-exists",    r"already approved|already has a keyframe candidate|reject it first|already current"),
    ("lineage-stale",      r"lineage|storyboard dependency|source beat package|script version|not approved from the current"),
    ("spend-token",        r"spend|SPEND|disclosure|token|binding|envelope|billing|unconfirmed"),
    ("batch-state",        r"batch|candidate|in-flight|MODEL-LIMITED|model-limited|attempts"),
    ("missing-artifact",   r"no approved|has no |is missing|not available|does not exist|no current|cannot be found|no plate|no keyframe|no voice|no take"),
    ("provider-capability",r"provider|resolution|duration must|does not verify|disabled|capability|endpoint|route"),
    ("input-invalid",      r"requires a plain-language|must be one of|invalid|malformed|required|must appear|needs at least"),
    ("contract-shape",     r"emission|dialogue|prompt|word|schema|contract"),
    ("concurrency",        r"lease|reload the scene|conflict|running|in use"),
]
def family(msg):
    m = msg or ""
    for name, pat in FAMILIES:
        if re.search(pat, m, re.I):
            return name
    return "other"

for r in rows:
    r["family"] = family(r["msg"])

fam = collections.Counter(r["family"] for r in rows)
print("\nBY FAMILY:")
for k, v in fam.most_common():
    print(f"  {v:4d}  {k}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "refusals.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=1, ensure_ascii=False))
print("\nwrote", out)

# Sample messages per family (deduped by first 70 chars) for the report.
print("\n=== SAMPLES ===")
for name, _ in FAMILIES + [("other", "")]:
    group = [r for r in rows if r["family"] == name]
    if not group:
        continue
    seen, shown = set(), 0
    print(f"\n--- {name} ({len(group)} sites)")
    for r in group:
        key = r["msg"][:70]
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        if shown > 12:
            print(f"    ... +{len(group) - 12} more sites")
            break
        print(f"  {r['file']}:{r['line']} {r['func']}() :: {r['msg'][:150]}")
