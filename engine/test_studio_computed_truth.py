#!/usr/bin/env python3
"""test_studio_computed_truth.py — THE SYSTEM COMPUTES THE RIGHT ANSWER AND THEN THROWS IT AWAY.

That sentence is the whole finding of the 2026-07-26 UX assessment, arrived at independently by
four assessors looking at four unrelated datasets. Not four bugs — one habit:

  · the creative room writes three named treatments and the reasoning that welded two of them
    together (21,537 + 8,958 characters for Scene 1) and the UI filed all of it under
    "Technical details", truncated at 4,000 characters of a ~145,000-character dump — and
    `"treatments"` begins at character 5,766, so the slice ended BEFORE the first treatment did;
  · the production package carries structured QC findings with exact field paths, and
    `grep -c "package.validation" app.html` returned 0 — rendered zero times, ever;
  · engine/cost_ledger.jsonl holds every real generation call ever made ($358.81 net over 340
    entries, one file rendered 28 times for $120.15) and `grep -c cost_ledger serve.py` returned
    0 — no route read it, so no screen could show it.

Each of those was already computed, already paid for, already on disk. None of it was rendered.
This file binds the rendering, so a future edit that quietly drops it fails a test instead.

It is a STATIC TEXT CHECK on purpose — no server, no browser, no network, no provider call —
the same convention test_studio_chair_table.py already established, so it runs in the ordinary
suite. The one exception is clearly marked: the spend reader's own attribution logic is
extracted from serve.py and executed against a synthetic ledger, because "a route exists" and
"the number it returns is right" are different claims.

    pytest test_studio_computed_truth.py -q
"""
import json
import pathlib
import re
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
APP = HERE.parent / "cb-studio" / "app.html"
SERVE = HERE.parent / "cb-studio" / "serve.py"


def _app():
    return APP.read_text()


def _app_code():
    """app.html with its `//` line comments stripped. Several of the strings these tests hunt for
    are QUOTED IN THE COMMENTS that explain why they were removed — so a naive text search finds
    its own documentation and fails. Only whole-line comments are dropped, which is enough here
    and cannot corrupt a template literal containing "//" (a URL, say) mid-line."""
    return "\n".join(l for l in APP.read_text().splitlines() if not l.lstrip().startswith("//"))


def _live_app_code():
    """`renderShotStage` (~370 lines) was superseded by renderShotRunner on 2026-07-23 and has
    been defined-but-never-called ever since; the 2026-07-26 assessment names it for deletion
    once its three un-approve buttons are harvested. Deleting it is not this pass's work, but a
    control nobody can reach must not be held to a rule about what a human sees. Excluded here
    BY NAME, and only while it stays genuinely dead — the assertion below fails the moment it is
    called again, which is exactly when its controls start mattering."""
    code = _app_code()
    marker = "\nfunction renderShotStage("
    if marker not in code:
        return code
    assert code.count("renderShotStage(") == 1, \
        "renderShotStage has a caller again — it is live code now, so every control in it " \
        "must satisfy the same rules as the rest of the panel; remove this exclusion"
    return code[:code.index(marker)]


def _serve():
    return SERVE.read_text()


# ── 1 · THE STORYBOARD TREATMENTS ────────────────────────────────────────────────────────

def test_the_treatments_are_rendered_not_only_dumped():
    """The three named approaches and the selection reasoning must reach a real surface."""
    a = _app()
    assert "function treatmentsHTML(" in a, "no renderer for the treatments exists"
    assert "PSB.treatments" in a, "nothing reads the treatments off the storyboard"
    assert "treatmentSelection" in a, "nothing reads the reasoning that chose one"
    # and it must actually be CALLED from the storyboard screen, not merely defined —
    # this codebase has a documented history of fully-built functions with zero call sites
    body = a[a.index("function renderStoryboardStage("):]
    body = body[:body.index("\nasync function pFireCreative(")]
    assert "treatmentsHTML()" in body, "treatmentsHTML is defined but never called"


def test_the_selection_reasoning_and_the_verdicts_are_rendered():
    a = _app()
    for key in ("showrunnerJudgement", "treatmentComparison"):
        assert key in a, f"{key} — a computed verdict with no render site"


def test_the_storyboard_raw_record_is_not_truncated():
    """`JSON.stringify(PSB,null,1).slice(0,4000)` is the exact line that hid the treatments.
    A truncation that discards 97% of a record is not a disclosure."""
    # Asserted on the RENDER SITE itself, not on a text search of the whole file: the offending
    # expression is quoted verbatim in two comments that exist to explain why it was removed, and
    # a search would keep finding its own documentation.
    a = _app_code()
    site = re.search(r"<pre class=\"techpre\">\$\{_esc\(JSON\.stringify\(PSB[^`]*", a)
    assert site, "the storyboard raw-record dump has gone missing entirely"
    assert ".slice(" not in site.group(0), \
        "the storyboard raw record is truncated again — this is what hid the treatments"


def test_the_treatment_fields_are_not_a_list_typed_into_the_ui():
    """Same rule the shot panel already lives under: the engine's own keys drive the render.
    A hardcoded field list silently drops any field the creative room starts writing."""
    a = _app()
    start = a.index("function treatmentsHTML(")
    body = a[start:a.index("function renderStoryboardStage(")]
    assert "Object.keys(t)" in body, \
        "treatmentsHTML must walk the treatment's own keys, never a list typed in app.html"
    for invented in ("visualGrammar", "cutPhilosophy", "cinematographerChallenge"):
        assert invented not in body, \
            f"{invented} is hardcoded in the renderer — the engine's table must drive this"


# ── 2 · package.validation ───────────────────────────────────────────────────────────────

def test_the_packages_own_qc_findings_are_rendered():
    """`grep -c "package.validation\\|pkg.validation" app.html` returned 0 on 2026-07-26."""
    a = _app()
    assert "SH_PKG.validation" in a, "nothing in the UI reads the package's validation block"
    assert "function valFor(" in a and "function valRowsHTML(" in a, \
        "no renderer for the QC findings exists"
    assert a.count("valRowsHTML(") >= 3, \
        "valRowsHTML is defined but barely called — findings must reach a real surface"


def test_a_qc_finding_is_attributed_by_shot_id_never_by_array_position():
    """The engine writes the shot id INTO the path — "shots[3](S1.SH4).camera". Attributing by
    the `shots[N]` index instead would mis-file every finding the moment a shot is promoted or
    inserted, which this pipeline does routinely."""
    a = _app()
    assert "_VAL_PATH_RE" in a, "no path parser for validation findings"
    m = re.search(r"const _VAL_PATH_RE=(/.*?/);", a)
    assert m, "_VAL_PATH_RE is not a plain regex literal any more — re-check this binding"
    pattern = m.group(1)
    assert r"\(" in pattern and r"\)" in pattern, \
        "the parser must read the (shotId) in the path, not the shots[N] index"


def test_no_qc_finding_can_be_dropped_for_want_of_somewhere_to_put_it():
    a = _app()
    assert "function valSceneWide(" in a, \
        "a finding whose path names no shot would have nowhere to appear"


# ── 3 · THE COST LEDGER ──────────────────────────────────────────────────────────────────

def test_a_route_reads_the_cost_ledger():
    """`grep -c cost_ledger serve.py` returned 0 on 2026-07-26 — 340 entries, $358.81, and no
    route in 2,700 lines read the file."""
    s = _serve()
    assert "/api/spend" in s, "no endpoint exposes what has actually been spent"
    assert "def spend_report(" in s, "no reader for the ledger"
    assert "cost_ledger" in s or "LEDGER_PATH" in s, "the ledger itself is still unread"


def test_the_spend_route_is_read_only():
    """This is an accounting surface, never a permission one — Julian's 2026-07-21 ruling
    ("if I press render it renders") is not reopened by showing him a number."""
    s = _serve()
    body = s[s.index("def spend_report("):s.index("def scene_lineage(")]
    for forbidden in ("open(", ".write(", ".write_text(", "os.replace", "json.dump("):
        assert forbidden not in body, f"spend_report must never write — found {forbidden}"


def test_the_shot_header_and_the_reject_button_both_carry_a_figure():
    """Reject authorises the next batch and is the most expensive control in the product. It
    carried no number at all."""
    a = _live_app_code()
    assert "shSpendFor(" in a, "the shot header cannot state what the shot has cost"
    assert "rejectCost" in a, "no cost figure is attached to the reject controls"
    # only the take-level reject reopens the shot into a new PAID batch; reject-voice /
    # reject-keyframe / reject-scenelook reopen a free, text-or-image step and correctly
    # carry no video figure.
    rejects = re.findall(r'<button[^>]*onclick="sh(?:Run\(.reject.,|RejectBatch)[^>]*>([^<]*)', a)
    live = [r for r in rejects if "Reject" in r]
    assert live, "no reject controls found — re-check this binding"
    for label in live:
        assert "rejectCost" in label, \
            f"a reject control names no cost: {label!r} — it authorises the next paid batch"


def test_the_spend_numbers_are_labelled_as_estimates_never_as_a_bill():
    a, s = _app(), _serve()
    assert "not a bill" in a, "the spend figure must not read as a billing record"
    assert '"estimate": True' in s or "'estimate': True" in s, \
        "the payload must declare itself an estimate"


# ── the one non-static check: does the reader actually attribute correctly ────────────────

def _spend_ns():
    """Execute serve.py's two ledger helpers in isolation. serve.py starts an HTTP server at
    import time, so it cannot be imported — the functions are extracted verbatim instead. The
    extraction is anchored on their own def lines, so a rename fails this test loudly rather
    than silently testing nothing."""
    s = _serve()
    start = s.index("_LEDGER_SHOT_RE = re.compile(")
    end = s.index("def scene_lineage(")
    ns = {"re": re, "json": json, "pathlib": pathlib, "ROOT": HERE.parent}
    exec(compile(s[start:end], "serve.py:ledger", "exec"), ns)
    return ns


def test_attribution_reads_the_real_filenames_this_pipeline_writes():
    attrib = _spend_ns()["_ledger_attribution"]
    cases = [
        ({"out": "Ep1_S1.SH2_c1.mp4"},               ("Ep1", "1", "S1.SH2")),
        ({"out": "Ep1_S1.SH2A_c1.mp4"},              ("Ep1", "1", "S1.SH2A")),
        ({"out": "Ep1_S1.SH10_c1.mp4"},              ("Ep1", "1", "S1.SH10")),
        ({"out": "Ep1_S1.SH1_keyframe.png"},         ("Ep1", "1", "S1.SH1")),
        ({"out": "vo_Ep1_1.B1.mp3"},                 ("Ep1", "1", None)),
        ({"out": "Ep1_S1_plate.png"},                ("Ep1", "1", None)),
        ({"out": "proof.mp4"},                       (None, None, None)),
        ({"out": None},                              (None, None, None)),
    ]
    for row, expected in cases:
        assert attrib(row) == expected, f"{row['out']!r} -> {attrib(row)} (expected {expected})"


def test_a_shot_never_absorbs_a_longer_shot_ids_spend():
    """S1.SH1 must not collect S1.SH10's money. A substring match would."""
    attrib = _spend_ns()["_ledger_attribution"]
    assert attrib({"out": "Ep1_S1.SH10_c1.mp4"})[2] == "S1.SH10"
    assert attrib({"out": "Ep1_S1.SH1_c1.mp4"})[2] == "S1.SH1"


def test_the_total_is_net_of_the_ledgers_own_reversals():
    """The real ledger carries negative `ledger_correction` rows reversing phantom test spend
    ($-200.24 of the 340 entries). A total that ignored them would overstate real spend by more
    than half, and would be the more alarming number — exactly the wrong error to make."""
    ns = _spend_ns()
    rows = [
        {"op": "seedance_ref2vid", "cost_usd": 4.551, "out": "Ep1_S1.SH1_c1.mp4"},
        {"op": "seedance_ref2vid", "cost_usd": 4.551, "out": "Ep1_S1.SH1_c1.mp4"},
        {"op": "seedance_ref2vid", "cost_usd": 4.551, "out": "proof.mp4"},
        {"op": "ledger_correction", "cost_usd": -4.551, "out": None,
         "meta": {"nonBillable": True, "correctsOut": "proof.mp4"}},
    ]
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "cost_ledger.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

        class _FakeCosts:
            LEDGER_PATH = str(p)
            RATES_UPDATED = "test"

        import sys
        sys.modules["cb_costs"] = _FakeCosts
        try:
            out = ns["spend_report"]("Ep1", "1")
        finally:
            del sys.modules["cb_costs"]

    assert round(out["totalUsd"], 3) == 9.102, out["totalUsd"]        # net, not 13.653 gross
    assert round(out["correctionsUsd"], 3) == -4.551
    assert out["shots"]["S1.SH1"]["calls"] == 2
    assert round(out["shots"]["S1.SH1"]["usd"], 3) == 9.102
    assert out["shots"]["S1.SH1"]["topFile"]["calls"] == 2, \
        "the most-repeated artefact must be reported — 28 fires of one file was invisible"


def test_a_torn_ledger_line_never_breaks_the_read():
    ns = _spend_ns()
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "cost_ledger.jsonl"
        p.write_text('{"op":"x","cost_usd":1.0,"out":"Ep1_S1.SH1_c1.mp4"}\n{"op":"trunc\n')

        class _FakeCosts:
            LEDGER_PATH = str(p)
            RATES_UPDATED = "test"

        import sys
        sys.modules["cb_costs"] = _FakeCosts
        try:
            out = ns["spend_report"]("Ep1", "1")
        finally:
            del sys.modules["cb_costs"]
    assert out["totalCalls"] == 1 and round(out["totalUsd"], 2) == 1.0


def test_a_missing_ledger_reports_nothing_rather_than_zero_spend():
    """A blank is honest when the ledger cannot be read; a confident $0.00 is not."""
    ns = _spend_ns()
    with tempfile.TemporaryDirectory() as d:
        class _FakeCosts:
            LEDGER_PATH = str(pathlib.Path(d) / "nope.jsonl")
            RATES_UPDATED = "test"

        import sys
        sys.modules["cb_costs"] = _FakeCosts
        try:
            out = ns["spend_report"]("Ep1", "1")
        finally:
            del sys.modules["cb_costs"]
    assert out["exists"] is False and out["shots"] == {}


# ── 4 · THE ONE-LINE WRAP BUG (fixed in 17f7f00; this is the floor under it) ──────────────

def test_no_bare_pre_can_typeset_as_an_unwrapped_slab():
    """`asText` emitted a bare <pre>: the PENDING branch landed in .rundecide-text (which has a
    pre rule) and wrapped; the APPROVED branch landed in .rowmore (which has none) and did not —
    so the text wrapped while you were deciding and unwrapped the moment you approved. Commit
    17f7f00 fixed it structurally by deleting the split. This is the floor under that fix: any
    <pre> nobody styled still wraps."""
    a = _app()
    assert re.search(r"\bpre\{[^}]*white-space:pre-wrap", a), \
        "no base rule guarantees a bare <pre> wraps"


def test_every_pre_in_the_shot_panel_wraps():
    """Belt and braces: every <pre> the app emits carries a class or inline style that wraps,
    or is covered by the base rule above."""
    a = _app()
    css = a[:a.index("</style>")]
    for m in re.finditer(r'<pre(\s[^>]*)?>', a[a.index("</style>"):]):
        attrs = (m.group(1) or "").strip()
        if not attrs:
            continue                                    # covered by the base rule, asserted above
        cls = re.search(r'class="([^"]+)"', attrs)
        style = re.search(r"style=[\"']([^\"']+)", attrs)
        wraps = bool(style and "pre-wrap" in style.group(1))
        if not wraps and cls:
            wraps = any(re.search(r"\." + re.escape(c) + r"\b[^{]*\{[^}]*white-space:pre-wrap", css)
                        or re.search(r"\." + re.escape(c) + r"\b\s+pre\{[^}]*white-space:pre-wrap", css)
                        for c in cls.group(1).split())
        assert wraps, f"<pre {attrs}> can typeset unwrapped"


# ── the standing rule these four all violate ─────────────────────────────────────────────

def test_the_studio_never_reintroduces_a_confirmation_gate_on_spend():
    """The assessment was explicit that money is an accounting problem, not a permission one.
    Every number added here is a FACT on a control, never a new dialog in front of it."""
    a = _app()
    start = a.index("const rejectCost=")
    window = a[start - 1400:start + 400]
    assert "confirm(" not in window, "a confirmation dialog was added to the reject path"
