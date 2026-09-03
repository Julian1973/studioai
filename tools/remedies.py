"""Assign every front-line refusal and every blocker to exactly one remedy. Prints the
coverage table and the appendix, so no count in the report is asserted rather than counted."""
import json, io, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(io.open(os.path.join(HERE, "reach.json"), encoding="utf-8"))

# remedy id -> (button label, what it does, input needed, cost)
REMEDIES = {
 "R1":  ("Lock cast",              "Attach the named character's identity reference from the asset library (or upload one) and re-lock canon — or declare the role a scripted stub staged off-frame, which canon already supports.", "which of the two; the image if attaching", "free"),
 "R2":  ("Refresh direction",      "Re-prepare that department from the current inputs and adopt it as the shot's direction.", "none", "one text call"),
 "R3":  ("Re-confirm / Rebuild",   "Inputs moved under an approval. Re-confirm re-approves the same artifact against current inputs (free); Rebuild regenerates it (disclosed).", "none for Re-confirm", "free / paid"),
 "R4":  ("Replace",                "Something is already awaiting a decision. Replace archives it with the reason and starts the new one in a single step.", "one sentence", "as the new step"),
 "R5":  ("Add the note",           "The action needs one plain-language sentence before it can run.", "one sentence", "free"),
 "R6":  ("Choose the candidate",   "Open the A/B chooser; Accept stays unavailable, with the reason shown, until a candidate is selected.", "pick A or B", "free"),
 "R7":  ("Re-seal the request",    "The sealed spend request went stale or was used. Cancel it and compile a fresh disclosure with the current cost.", "none", "free until approved"),
 "R8":  ("Resume / Abandon batch", "A batch is mid-flight or pending. Resume with its original token, or abandon it (releasing the provider claims) to seal a fresh one.", "none / reason to abandon", "free"),
 "R9":  ("Reopen the take",        "Archive the accepted take with the correction and reopen the shot for a new render.", "one sentence", "free (re-render is separate)"),
 "R10": ("Reopen with a redesign", "Model-limited: record what was redesigned and buy one more render.", "one sentence", "free (render separate)"),
 "R11": ("Go to the step that is missing", "The blocking work belongs to an earlier stage or another shot. The button names it and takes you there, already selected.", "none", "free"),
 "R12": ("Carry onto the canon lock", "The approved work is behind a canon re-lock. Carry the beat package, vision, storyboards and production packages forward unchanged.", "none", "free"),
 "R13": ("Promote Story & Direction", "Build or refresh the production handover from the approved storyboard, auto-repairing the field-scoped validator failures first.", "none", "free"),
 "R14": ("Split shot",             "The direction needs more time or complexity than one 30-second unit allows. Split it into two units at a named boundary and re-promote.", "where to split", "free"),
 "R15": ("Lock the cut",           "Confirm the Director's Seat cut for this scene so the master can build.", "none", "free"),
 "R16": ("Fix configuration",      "A key, ffmpeg or a billing confirmation is missing. Billing is a confirm button; a key or ffmpeg names the exact file and line to change.", "varies", "free"),
 "R17": ("Reload and retry",       "Another write landed first. Reload the scene and re-apply automatically; only ask if it fails twice.", "none", "free"),
 "R18": ("Restore the compiled prompt", "The saved WATCH working prompt is stale. Restore the compiled one, or re-save after refreshing direction.", "none", "free"),
 "R19": ("Bind the reference",     "A required prop/reference is not bound to its role. Open the picker for that exact role.", "pick the asset", "free"),
 "R20": ("Rebuild review media",   "Review frames or the review audio could not be read. Rebuild them from the accepted take.", "none", "free"),
 "R21": ("Fix the storyboard field", "A design/contract validator rejected a specific field. Open the beat editor at that field with the validator's own words.", "the corrected text", "free"),
 "R22": ("Re-run the scene direction", "The Director's own output broke a hard story contract (dropped beats, unknown participant). Re-run the scene from the note.", "optional note", "paid text pass"),
 "R23": ("Retry the provider",     "The provider failed or returned nothing usable. Retry once; if it fails again, say so with the provider's message.", "none", "as the step"),
 "PASS":("(re-raise — inherits the inner remedy)", "A bare pass-through of another refusal's message; the remedy is whichever refusal it wrapped.", "-", "-"),
 "XX":  ("(no remedy — internal invariant)", "Unreachable from a button unless the UI sends a malformed request; keep as a loud refusal.", "-", "-"),
}

# ordered rules: first match wins
RULES = [
 ("R1",  r"identity pack|resolvable identity reference|CANON LOCK REFUSED|locked roster|not production-ready"),
 ("R12", r"canon rebase|not approved from the current story-canon|story-canon lock|dependency signature is missing or stale|LINEAGE MISSING|beat package .*(missing|changed)|episode vision does not match|no approved beat package"),
 ("R14", r"performance budget is overloaded|timed beats|unit ceiling|complexity"),
 ("R2",  r"Prepare current .*direction|typed opening-frame layout|direction is stale|Look Development direction|approved Cinematography direction .*is missing|Cinematography (cast|style|placements)|animation provider prompt is not production-ready|animation dialogue synthesis contract"),
 ("R3",  r"stale against its direct inputs|direct input\(s\) changed|does not match current direction|no longer match|candidate is stale|storyboard is no longer approved|signed Director shot card is stale|amendment no longer matches"),
 ("R4",  r"already has a keyframe candidate|already has work awaiting|already approved; reject it first|voice take is already approved|already awaits review|already has a working Scene Look|Scene Look candidate awaiting|pose candidate is awaiting|already has a finished keyframe|complete voice track is already approved"),
 ("R6",  r"A/B selection|selected SEE candidate does not match|no pending SEE candidate"),
 ("R7",  r"spend token|new disclosure|sealed envelope|changed on disk after the disclosure|changed after disclosure|binding mismatch|SPEND NOT APPROVED|comparison settings differ|DRY RUN"),
 ("R8",  r"in-flight batch|candidate batch pending|no candidate batch pending|batch is currently generating|resumable|transactionally completed artifact|candidate must be 1"),
 ("R9",  r"is already approved; reject it first to re-fire|no accepted animation take to reopen"),
 ("R10", r"MODEL-LIMITED|model-limited"),
 ("R5",  r"requires a plain-language|requires a written reason|needs a plain-language|cannot be blank|category must be one of|verdict must be"),
 ("R11", r"has no APPROVED keyframe|not approved\+harvested|no previous final frame|first shot; there is no previous|approved voice is required|no voice track to (approve|reject)|no actual (keyframe|animation) media|unapproved shots|not a current signed working anchor|relays off|no ElevenLabs voiceId|human-approved Director storyboard|no signed Director shot card|lacks (scoped|forward) directing contracts|predates directing standard|emotional North Star|no current QC-passed post master|scene cut source is unavailable|inherits its opening frame|is a relay shot"),
 ("R15", r"lock the current Director's Seat cut|scene cut cannot be locked"),
 ("R16", r"billing profile|UNCONFIRMED|API_KEY|ffmpeg"),
 ("R17", r"reload the scene and retry"),
 ("R18", r"working prompt is stale"),
 ("R19", r"continuity prop authority|reference slot text conflicts|reference file is missing|resolves outside|openingFrameOverride|library item no longer exists|no uploaded file found|reference_path does not exist|unknown (opening-frame|Scene Look) source"),
 ("R20", r"could not extract review frames|no visible frames|cannot restore approved HEAR|scene look record is unreadable|review media or voice master is missing"),
 ("R21", r"design validation|fresh validation of the CURRENT package|not a playable stage|playable-stage and identity screen|duplicates|does not name each approved|preflight failed|is not active in the current package|multi-character WATCH shot"),
 ("R22", r"BEAT PASS|BEAT PARTICIPANT|dialogue coverage is not exact|source-event partition"),
 ("R23", r"Image API returned no candidates|provider|locked to Seedream|post build failed"),
 ("PASS", r"^REFUSED . \{\}$"),
 ("R11", r"has no keyframe candidate awaiting approval|has no specialist candidate awaiting a decision|has dialogue but"),
 ("R2",  r"placements for .* do not name each approved"),
 ("R7",  r"existing spend disclosure before overriding"),
 ("R13", r"scoped Director amendment|scoped v4 directing contracts"),
]

def remedy(msg):
    for rid, pat in RULES:
        if re.search(pat, msg, re.I):
            return rid
    return "XX"

# ---- front-line refusals (depth<=1, user-facing wording) ----
rows, seen = [], set()
for act in sorted(d["actions"]):
    for r in d["actions"][act]:
        if r["depth"] > 1 or not r["msg"].startswith(("REFUSED", "Law", "CANON", "SCRIPT", "BEAT")):
            continue
        if r["at"] in seen:
            for x in rows:
                if x["at"] == r["at"]: x["acts"].add(act)
            continue
        seen.add(r["at"])
        rows.append({"at": r["at"], "msg": r["msg"], "acts": {act}, "remedy": remedy(r["msg"])})

# ---- blockers ----
BLOCKER_REMEDY = {
 "CANON_LOCK_REQUIRED":"R1","VOICE_ID_MISSING":"R1",
 "CINEMATOGRAPHY_NOT_CURRENT":"R2","CINEMATOGRAPHY_NOT_APPROVED":"R2","VOICE_DIRECTION_NOT_CURRENT":"R2",
 "VOICE_DIRECTION_NOT_APPROVED":"R2","ANIMATION_DIRECTION_NOT_CURRENT":"R2","ANIMATION_DIRECTION_NOT_APPROVED":"R2",
 "LOOK_DIRECTION_NOT_CURRENT":"R2","LOOK_DIRECTION_NOT_APPROVED":"R2","STALE_ANIMATION_DIRECTION":"R2",
 "KEYFRAME_NOT_CURRENT":"R3","VOICE_TAKE_NOT_CURRENT":"R3","ANIMATION_TAKE_NOT_CURRENT":"R3",
 "SCENE_LOOK_NOT_CURRENT":"R3","SHOT_NOT_READY":"R3",
 "KEYFRAME_NOT_APPROVED":"R11","VOICE_TAKE_NOT_APPROVED":"R11","ANIMATION_NOT_APPROVED":"R11",
 "SCENE_LOOK_NOT_APPROVED":"R11","RELAY_FRAME_NOT_READY":"R11","DIRECTOR_REVIEW_NOT_CURRENT":"R11",
 "TIMING_SLATE_NOT_CURRENT":"R11","SCENE_LOOK_REFERENCE_REQUIRED":"R19",
 "STORY_INTAKE_APPROVAL_REQUIRED":"R12","STALE_PRODUCTION_GRAPH":"R12","STALE_PACKAGE":"R12",
 "PRODUCTION_PACKAGE_MISSING":"R13","PACKAGE_VALIDATION":"R13","STORYBOARD_NOT_APPROVED":"R13",
 "CONFIG_FAL_KEY":"R16","CONFIG_ELEVENLABS_KEY":"R16","CONFIG_FFMPEG":"R16",
 "SHOW_PROFILE_CONTENT_MISSING":"R16",
}
for b in d["blockers"]:
    b["remedy"] = BLOCKER_REMEDY.get(b["code"], "XX")

cnt_r = collections.Counter(r["remedy"] for r in rows)
cnt_b = collections.Counter(b["remedy"] for b in d["blockers"])
print(f"front-line refusals: {len(rows)}   blockers: {len(d['blockers'])}\n")
print(f"{'id':4} {'button':30} {'refusals':>8} {'blockers':>8}  input")
for rid, (label, _what, need, _cost) in REMEDIES.items():
    if not cnt_r[rid] and not cnt_b[rid]: continue
    print(f"{rid:4} {label:30} {cnt_r[rid]:8d} {cnt_b[rid]:8d}  {need}")
print(f"\nunmapped refusals (XX): {cnt_r['XX']}   unmapped blockers: {cnt_b['XX']}")
for r in rows:
    if r["remedy"] == "XX":
        print(f"   {r['at']:22} {r['msg'][:120]}")
for b in d["blockers"]:
    if b["remedy"] == "XX":
        print(f"   BLOCKER {b['code']}")

io.open(os.path.join(HERE, "remedies.json"), "w", encoding="utf-8").write(json.dumps(
    {"rows": [{**r, "acts": sorted(r["acts"])} for r in rows],
     "blockers": d["blockers"], "remedies": REMEDIES}, indent=1, ensure_ascii=False))
print("\nwrote remedies.json")
