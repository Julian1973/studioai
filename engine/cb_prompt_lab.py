"""Deterministic prompt analysis and governed render-rating helpers.

The Prompt Lab compares authored direction with observed media. It never calls a model,
rewrites a prompt, changes an approval, or contacts a media provider. Human ratings are
evidence tied to an exact prompt hash and asset hash; they are not production gates.
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict

import cb_emission_conformance as emission


SCHEMA_VERSION = 7
SEEDANCE_GUIDE_PROFILE = "bytedance-seedance-2.5-2026-08-07"
SEEDANCE_GUIDE_SOURCE = {
    "title": "Dreamina Seedance 2.5 User Guide",
    "url": "https://docs.byteplus.com/en/docs/ModelArk/2607689",
    "larkUrl": "https://bytedance.larkoffice.com/docx/A88jd0B47oAd8zxWp5ycZFMfnxh",
    "productUrl": "https://dreamina.capcut.com/seedance/seedance-2-5",
    "apiQualificationUrl": "https://docs.byteplus.com/en/docs/modelark/1159178",
    "skill": ".agents/skills/sd25-pe",
    "lastUpdated": "2026-08-07",
    "scope": "Official Dreamina/BytePlus prompt guidance; executable API schema, pricing and account access are separate",
}
SEEDANCE_GUIDE_LIMITS = {
    "standardDurationSec": {"minimum": 4, "maximum": 30},
    "betaLongVideoDurationSec": {"minimum": 5, "maximum": 180},
    "extensionDurationSec": {"minimum": 4, "maximum": 30},
    "outputResolutions": ["480p", "720p"],
    "maxCombinedInputs": 50,
    "maxImages": 30,
    "maxVideos": 10,
    "maxVideoDurationSec": 30,
    "maxAudioClips": 10,
    "maxAudioDurationSec": 30,
}
SEEDANCE_GUIDE_SEMANTICS = {
    "timestampControl": (
        "Time ranges allocate pacing and exact time points improve alignment; they are not "
        "a frame-accurate edit guarantee."
    ),
    "extensionPreservation": (
        "Preserve the source and match its boundary state, but review the join; generated "
        "continuation and boundary frames are not guaranteed pixel-identical."
    ),
    "negativeInstructions": (
        "Explicit forbidden items improve reliability but remain probabilistic and require review."
    ),
    "identityStability": (
        "Multi-character consistency is improved, not self-approving; identity and count still "
        "require visual review."
    ),
    "longVideoRoute": (
        "The 5-180 second mode is a Dreamina beta product capability, not a qualified Studio API route."
    ),
    "audioOnly": (
        "Dreamina product guidance describes audio-only creation; the current BytePlus Seedance "
        "2.0 API still requires at least one image or video reference."
    ),
    "cleanOutput": (
        "Dreamina advertises cleaner 4K output; the executable provider contract remains the "
        "authority for resolution and every render still requires QC."
    ),
    "watermarkPolicy": (
        "The Studio never uses generative watermark removal as a production shortcut; source "
        "footage must be owned or licensed and delivered clean."
    ),
}
SEEDANCE_TASK_MODES = {
    "text-to-video", "reference-to-video", "thirty-second-video",
    "ultra-long-video", "video-edit", "extend-forward", "extend-backward",
    "transition", "first-last-frame", "storyboard-grid", "blockout-render",
}
VALID_ARTIFACT_TYPES = {"keyframe", "animation"}
VALID_OVERALL_READS = {"miss", "partial", "lands"}

DIMENSIONS = OrderedDict([
    ("beatDelivery", "Beat lands"),
    ("actingAndPerformance", "Acting and performance"),
    ("physicalCausality", "Physical cause and effect"),
    ("timingAndReaction", "Timing and reaction"),
    ("cameraAndEdit", "Camera and edit"),
    ("compositionAndContinuity", "Composition and continuity"),
    ("identityAndReferenceUse", "Identity and references"),
    ("finishAndProductionValue", "Finish and production value"),
])

KEYFRAME_DIMENSIONS = tuple(
    name for name in DIMENSIONS if name not in {"physicalCausality", "timingAndReaction"}
)
ANIMATION_DIMENSIONS = tuple(DIMENSIONS)

_CATEGORY_PATTERNS = OrderedDict([
    ("intent", re.compile(
        r"\b(beat|purpose|moment|realise|realize|decide|discover|want|tries?|fails?|"
        r"wins?|loses?|audience|feeling|emotional|comic|funny|deadpan|payoff)\b", re.I)),
    ("identity", re.compile(
        r"\b(identity|canon|reference|proportion|relative scale|silhouette|markings?|"
        r"costume|character design|facial features?)\b|@图\d+", re.I)),
    ("composition", re.compile(
        r"\b(foreground|midground|background|depth|layer|negative space|occlusion|"
        r"composition|framing|screen (?:left|right)|profile|three-quarter|wide|medium|"
        r"close[- ]?up|two-shot|establishing)\b", re.I)),
    ("action", re.compile(
        r"\b(steps?|turns?|leans?|reaches?|grabs?|pulls?|pushes?|falls?|lands?|hits?|"
        r"crosses?|moves?|stops?|throws?|catches?|opens?|closes?|enters?|exits?)\b", re.I)),
    ("causality", re.compile(
        r"\b(because|causing|which makes|so that|therefore|as a result|trigger(?:s|ing)?|"
        r"forces?|until)\b", re.I)),
    ("performance", re.compile(
        r"\b(glance|blink|breath|breathes?|swallows?|flinch|hesitat|jaw|eyes?|eyebrow|"
        r"shoulders?|posture|expression|reaction|smirk|grin|frown|stare|beat of silence)\b", re.I)),
    ("timing", re.compile(
        r"\b(before|after|then|while|holds? for|pause|waits?|suddenly|slowly|quickly|"
        r"half-beat|two-beat|reaction beat|settles?|interrupts?)\b", re.I)),
    ("camera", re.compile(
        r"\b(camera|lens|\d{2,3}mm|doll(?:y|ies)|pans?|tilts?|tracks?|trucks?|orbits?|zooms?|handheld|"
        r"locked[- ]?off|rack focus|depth of field|cut to|match cut|single take)\b", re.I)),
    ("look", re.compile(
        r"\b(light|lighting|shadow|rim|bounce|glow|material|texture|surface|fur|glass|"
        r"metal|wood|specular|diffuse|volumetric|colour|color|palette|grade|render)\b", re.I)),
    ("continuity", re.compile(
        r"\b(opening frame|first frame|starts? on|begins? on|landing image|lands? on|"
        r"ends? on|final frame|closing frame|handoff|continuity|screen direction)\b", re.I)),
    ("audio", re.compile(r"@Audio\d+|\b(audio|dialogue|voice|lip[- ]?sync|mouth)\b", re.I)),
    ("constraint", re.compile(
        r"\b(no|not|never|without|avoid|preserve|must|keep|do not|don't|unchanged|only)\b", re.I)),
])

_GENERIC_POLISH = re.compile(
    r"\b(cinematic|beautiful|stunning|amazing|epic|premium|magical|dynamic|high quality|"
    r"award[- ]winning|masterpiece)\b", re.I)
_CAMERA_MOVE = re.compile(
    r"\b(pans?|doll(?:y|ies)|tracks?|trucks?|orbits?|zooms?|tilts?|handheld)\b", re.I)
_CAMERA_LOCK = re.compile(r"\b(locked[- ]?off|camera (?:is )?(?:locked|still|static)|no camera movement)\b", re.I)
_NEGATIVE = re.compile(r"\b(no|not|never|without|avoid|do not|don't)\b", re.I)
_REFERENCE_TOKEN = re.compile(r"@(图|image|figure|audio|video)\s*(\d+)", re.I)
_REFERENCE_ROLE_WORDS = re.compile(
    r"\b(only|defines?|controls?|provides?|corresponds? to|used for|sole (?:source|authority)|"
    r"strictly (?:maintain|lock)|maintains?|locks?|"
    r"is the (?:first|last|opening|closing|source))\b", re.I)
_REFERENCE_EXCLUSION_WORDS = re.compile(
    r"\b(only|do not use|don't use|must not|exclude|without (?:the|its))\b", re.I)
_REQUEST_PARAMETER_WORDS = re.compile(
    r"\b(aspect ratio|resolution|model(?: id| version)?|duration\s*:|"
    r"480p|720p|1080p|2160p)\b|(?<!\d)(?:16:9|9:16|1:1)(?!\d)", re.I)
_TIME_RANGE = re.compile(
    r"(?<!\d)(\d+(?::\d{1,2}(?:\.\d+)?)?|\d+(?:\.\d+)?)"
    r"\s*(?:s(?:ec(?:ond)?s?)?\s*)?(?:-|–|—|to)\s*"
    r"(\d+(?::\d{1,2}(?:\.\d+)?)?|\d+(?:\.\d+)?)"
    r"\s*(?:s|sec(?:ond)?s?)?\b",
    re.I)
_STAGE_HEADING = re.compile(
    r"(?im)^\s*(?:\[\s*Stage\s+(\d+)(?:\s*\|[^\]]*)?\s*\]|"
    r"Stage\s+(\d+)\s*:\s*[^\n]*)\s*$")

_FEEDBACK_PATTERNS = OrderedDict([
    ("story-and-direction", re.compile(
        r"\b(direction|story|storyboard|script|beat|payoff|joke|funny|emotion|rewrite)\b", re.I)),
    ("camera-and-composition", re.compile(
        r"\b(camera|angle|shot|frame|framing|tight|wide|narrow|close[- ]?up|dolly|"
        r"pan|lens|screen side|foreground|background)\b", re.I)),
    ("identity-and-references", re.compile(
        r"\b(identity|reference|canon|character|glasses|proportion|scale|look|wrong bee)\b", re.I)),
    ("acting-and-emotion", re.compile(
        r"\b(deadpan|smile|sigh|shrug|pose|proud|surprise|expression|reaction|"
        r"performance|face|heart)\b", re.I)),
    ("action-and-physics", re.compile(
        r"\b(crash|impact|fall|land|flower|somersault|move|movement|leaves? frame|"
        r"cause|weight|physical)\b", re.I)),
    ("timing-and-pacing", re.compile(
        r"\b(timing|pace|late|later|early|delay|second|hold|quick|slow|rhythm)\b", re.I)),
    ("dialogue-and-audio", re.compile(
        r"\b(dialogue|line|voice|audio|lip[- ]?sync|mouth|sound|distance|heard)\b", re.I)),
    ("finish-and-delivery", re.compile(
        r"\b(quality|best|good|480p|720p|1080p|resolution|finish|production|keeper)\b", re.I)),
])

_CORRELATION_AXES = {
    "animation": (
        {
            "key": "storyBeat",
            "label": "Story beat and laugh",
            "sources": (("purpose",),),
            "promptTags": ("intent", "action"),
            "matchTerms": ("pace", "wreck", "crash", "joke", "realises"),
            "feedbackTopics": ("story-and-direction",),
            "ratingDimension": "beatDelivery",
        },
        {
            "key": "performance",
            "label": "Character performance",
            "sources": (("performanceAssignment",), ("principalPerformanceApproved",)),
            "promptTags": ("performance", "timing"),
            "matchTerms": ("antennae", "wings", "glance", "superhero", "pose", "busy"),
            "feedbackTopics": ("acting-and-emotion", "timing-and-pacing"),
            "ratingDimension": "actingAndPerformance",
        },
        {
            "key": "physics",
            "label": "Action and physical cause",
            "sources": (("physicalStaging", "contactAndWeight"),
                        ("animationTimingApproved",)),
            "promptTags": ("action", "causality"),
            "matchTerms": ("clips", "yaw", "yaws", "compresses", "compressing", "bows", "bowing", "flings", "somersaults", "rebound"),
            "feedbackTopics": ("action-and-physics",),
            "ratingDimension": "physicalCausality",
        },
        {
            "key": "timingDialogue",
            "label": "Timing and dialogue",
            "sources": (("dialogueTimingProse",), ("tempoDesign",)),
            "promptTags": ("timing", "audio", "performance"),
            "matchTerms": ("audio1", "silence", "speech", "mouth", "song", "line"),
            "feedbackTopics": ("timing-and-pacing", "dialogue-and-audio"),
            "ratingDimension": "timingAndReaction",
        },
        {
            "key": "camera",
            "label": "Camera and edit",
            "sources": (("camera",),),
            "promptTags": ("camera", "composition"),
            "matchTerms": ("front", "held", "reframe", "dolly", "zenny", "frame"),
            "feedbackTopics": ("camera-and-composition",),
            "ratingDimension": "cameraAndEdit",
        },
        {
            "key": "continuity",
            "label": "Opening and continuity",
            "sources": (("openingPose",), ("continuityProseOut",)),
            "promptTags": ("continuity", "composition"),
            "matchTerms": ("opening", "positions", "distance", "alone", "frame", "pollen"),
            "feedbackTopics": ("camera-and-composition",),
            "ratingDimension": "compositionAndContinuity",
        },
        {
            "key": "identity",
            "label": "Character and world lock",
            "sources": (("referenceRolesProse",),),
            "promptTags": ("identity", "look"),
            "matchTerms": ("reference", "fuzzby", "zenny", "identity", "proportions", "world"),
            "feedbackTopics": ("identity-and-references",),
            "ratingDimension": "identityAndReferenceUse",
        },
        {
            "key": "finish",
            "label": "Final emotional button",
            "sources": (("visualPayoff",), ("feltIntent",)),
            "promptTags": ("intent", "performance", "continuity", "look"),
            "matchTerms": ("shrug", "deadpan", "corner", "smile", "superhero", "pose"),
            "feedbackTopics": ("acting-and-emotion", "finish-and-delivery"),
            "ratingDimension": "finishAndProductionValue",
        },
    ),
    "keyframe": (
        {
            "key": "storyBeat",
            "label": "Story beat",
            "sources": (("purpose",),),
            "promptTags": ("intent", "action"),
            "matchTerms": ("beat", "payoff", "joke", "emotion"),
            "feedbackTopics": ("story-and-direction",),
            "ratingDimension": "beatDelivery",
        },
        {
            "key": "performance",
            "label": "Character performance",
            "sources": (("performanceAssignment",), ("openingPose",)),
            "promptTags": ("performance", "timing"),
            "matchTerms": ("eyes", "expression", "pose", "posture", "glance"),
            "feedbackTopics": ("acting-and-emotion",),
            "ratingDimension": "actingAndPerformance",
        },
        {
            "key": "camera",
            "label": "Camera and composition",
            "sources": (("camera",), ("firstFramePlan",)),
            "promptTags": ("camera", "composition"),
            "matchTerms": ("camera", "lens", "frame", "foreground", "background"),
            "feedbackTopics": ("camera-and-composition",),
            "ratingDimension": "cameraAndEdit",
        },
        {
            "key": "continuity",
            "label": "Opening and continuity",
            "sources": (("openingPose",), ("continuityProseIn",)),
            "promptTags": ("continuity", "composition"),
            "matchTerms": ("opening", "frame", "position", "screen", "continuity"),
            "feedbackTopics": ("camera-and-composition",),
            "ratingDimension": "compositionAndContinuity",
        },
        {
            "key": "identity",
            "label": "Character and world lock",
            "sources": (("referenceRolesProse",),),
            "promptTags": ("identity", "look"),
            "matchTerms": ("reference", "identity", "proportions", "fuzzby", "zenny", "world"),
            "feedbackTopics": ("identity-and-references",),
            "ratingDimension": "identityAndReferenceUse",
        },
        {
            "key": "finish",
            "label": "Finish and production value",
            "sources": (("feltIntent",), ("visualPayoff",)),
            "promptTags": ("look", "composition", "intent"),
            "matchTerms": ("light", "material", "texture", "emotion", "payoff"),
            "feedbackTopics": ("finish-and-delivery",),
            "ratingDimension": "finishAndProductionValue",
        },
    ),
}

_CORRELATION_STOPWORDS = {
    "about", "after", "again", "against", "also", "been", "before", "being",
    "both", "camera", "could", "does", "each", "every", "from", "have", "into",
    "itself", "never", "only", "other", "same", "should", "their", "there", "these",
    "they", "this", "through", "under", "until", "very", "what", "when", "where",
    "which", "while", "with", "without", "would", "your",
}


def _normalise(text):
    return re.sub(r"[^a-z0-9@']+", " ", str(text or "").lower()).strip()


def _sentences(prompt):
    parts = re.split(r"(?<=[.!?])\s+|[\r\n]+", str(prompt or "").strip())
    return [part.strip() for part in parts if part.strip()]


def _reference_key(value):
    match = _REFERENCE_TOKEN.search(str(value or ""))
    if not match:
        return None
    kind = ("image" if match.group(1).lower() in {"图", "image", "figure"}
            else match.group(1).lower())
    return f"{kind}:{int(match.group(2))}"


def _section_body(text, heading):
    match = re.search(
        rf"(?ims)^\s*(?:Module\s+\d+\s*:\s*)?\[{re.escape(heading)}\]"
        rf"\s*(?:\([^\n]*\))?\s*(.*?)(?=^\s*(?:Module\s+\d+\s*:\s*)?"
        rf"\[[^\]]+\].*$|^\s*Stage\s+\d+\s*:|\Z)",
        str(text or ""))
    return match.group(1).strip() if match else ""


def _first_section_body(text, headings):
    for heading in headings:
        body = _section_body(text, heading)
        if body:
            return body, heading
    return "", ""


def _stage_matches(text):
    return list(_STAGE_HEADING.finditer(str(text or "")))


def _stage_number(match):
    return int(match.group(1) or match.group(2))


def _stage_blocks(text, matches):
    blocks = []
    tail_section = re.compile(
        r"(?im)^\s*\[(?:Global Supplement|Overall Supplement|Maintain Consistency|Audio)\]"
    )
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        tail = tail_section.search(text, match.end(), end)
        if tail:
            end = tail.start()
        blocks.append(text[match.end():end])
    return blocks


def _reference_entries(reference_contract):
    entries = []
    for item in reference_contract or []:
        if isinstance(item, str):
            tag, role = item, ""
        else:
            tag = item.get("assetTag") or item.get("tag") or ""
            role = item.get("role") or item.get("controls") or ""
        key = _reference_key(tag)
        if key and not any(existing["key"] == key for existing in entries):
            entries.append({"key": key, "assetTag": str(tag), "role": str(role)})
    return entries


def _time_value(value):
    value = str(value)
    if ":" not in value:
        return float(value)
    minutes, seconds = value.split(":", 1)
    return float(minutes) * 60 + float(seconds)


def analyze_seedance_prompt_contract(prompt, *, task_mode="reference-to-video",
                                      reference_contract=None, duration_sec=None,
                                      dialogue_lines=None, stage_plan=None):
    """Compare a prompt with the official guide and the Studio's production policy.

    This is deterministic authoring analysis only. Provider availability, account access,
    prices and executable request limits remain owned by ``cb_providers`` and spend preflight.
    """
    if task_mode not in SEEDANCE_TASK_MODES:
        raise ValueError("unsupported Seedance task mode")
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("prompt cannot be blank")
    dialogue_lines = list(dialogue_lines or [])
    duration_value = None
    duration_numeric = duration_sec is None
    if duration_sec is not None:
        try:
            duration_value = float(duration_sec)
            duration_numeric = True
        except (TypeError, ValueError):
            duration_numeric = False
    # Seedance 2.5 guidance treats stages as the default narrative control. Time ranges
    # are useful for critical handoffs, entrances, exits, transitions or explicit audio
    # cues, but duration alone must not force timestamped prompt copy.
    timestamp_required = False
    staged_generation_modes = {
        "text-to-video", "reference-to-video", "thirty-second-video",
        "ultra-long-video",
    }
    expected_refs = _reference_entries(reference_contract)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    line_refs = []
    for line in lines:
        keys = {_reference_key(match.group(0)) for match in _REFERENCE_TOKEN.finditer(line)}
        line_refs.append((line, {key for key in keys if key}))
    used_refs = []
    for match in _REFERENCE_TOKEN.finditer(text):
        key = _reference_key(match.group(0))
        if key and key not in used_refs:
            used_refs.append(key)
    if not expected_refs:
        expected_refs = [{"key": key, "assetTag": key.replace(":", " "), "role": ""}
                         for key in used_refs]

    checks = []

    def add(code, label, ok, detail, action="", *, required=True,
            authority="official-guide"):
        checks.append({
            "code": code,
            "label": label,
            "status": "pass" if ok else "needs-work",
            "required": bool(required),
            "authority": authority,
            "detail": detail,
            "nextAction": "" if ok else action,
        })

    goal_headings = {
        "text-to-video": ("One-Sentence Summary", "Generation Goal"),
        "reference-to-video": ("One-Sentence Summary", "Generation Goal"),
        "thirty-second-video": ("One-Sentence Summary", "Generation Goal"),
        "ultra-long-video": ("Story Overview", "One-Sentence Summary", "Generation Goal"),
        "video-edit": ("Edit Goal",),
        "extend-forward": ("Extension Goal",),
        "extend-backward": ("Extension Goal",),
        "transition": ("Transition Goal",),
        "first-last-frame": ("Generation Goal", "One-Sentence Summary"),
        "storyboard-grid": ("Generation Goal", "One-Sentence Summary"),
        "blockout-render": ("Generation Goal", "One-Sentence Summary"),
    }[task_mode]
    goal_body, goal_heading = _first_section_body(text, goal_headings)
    expected_goal = " or ".join(f"[{heading}]" for heading in goal_headings)
    add(
        "goal", "One-sentence story summary", bool(goal_body),
        f"[{goal_heading}] states the central event." if goal_body else
        f"No populated {expected_goal} section was found.",
        f"Add {expected_goal} naming subject, location, event, style and any essential camera idea.")

    missing_refs, unmapped_refs, unscoped_visual_refs = [], [], []
    for entry in expected_refs:
        matching = [line for line, keys in line_refs if entry["key"] in keys]
        if not matching:
            missing_refs.append(entry["assetTag"])
            continue
        if not any(_REFERENCE_ROLE_WORDS.search(line) for line in matching):
            unmapped_refs.append(entry["assetTag"])
        if not entry["key"].startswith("audio:") and not any(
                _REFERENCE_EXCLUSION_WORDS.search(line) for line in matching):
            unscoped_visual_refs.append(entry["assetTag"])
    refs_required = task_mode in {
        "reference-to-video", "video-edit", "extend-forward", "extend-backward",
        "transition", "first-last-frame", "storyboard-grid", "blockout-render",
    }
    refs_ok = (bool(expected_refs) or not refs_required) and not (
        missing_refs or unmapped_refs or unscoped_visual_refs)
    ref_problems = []
    if not expected_refs and refs_required:
        ref_problems.append("no expected references were supplied")
    if missing_refs:
        ref_problems.append("missing " + ", ".join(missing_refs))
    if unmapped_refs:
        ref_problems.append("role not stated for " + ", ".join(unmapped_refs))
    if unscoped_visual_refs:
        ref_problems.append("no exclusion or only-scope for " +
                            ", ".join(unscoped_visual_refs))
    add(
        "reference-roles", "Reference roles", refs_ok,
        (f"All {len(expected_refs)} expected references are individually bound and scoped."
         if refs_ok else "; ".join(ref_problems)),
        "Bind every asset tag on its own line: what it defines, plus what it must not contribute.",
        required=refs_required or bool(expected_refs))

    reference_counts = {"image": 0, "video": 0, "audio": 0}
    for entry in expected_refs:
        kind = entry["key"].split(":", 1)[0]
        if kind in reference_counts:
            reference_counts[kind] += 1
    limits_ok = (
        reference_counts["image"] <= SEEDANCE_GUIDE_LIMITS["maxImages"] and
        reference_counts["video"] <= SEEDANCE_GUIDE_LIMITS["maxVideos"] and
        reference_counts["audio"] <= SEEDANCE_GUIDE_LIMITS["maxAudioClips"]
    )
    add(
        "reference-limits", "Official reference-count limits", limits_ok,
        (f"Mapped {reference_counts['image']} image(s), {reference_counts['video']} video(s) "
         f"and {reference_counts['audio']} audio clip(s)."),
        "Keep one request within 30 images, 10 reference videos and 10 audio clips; "
        "the executable provider may be stricter.",
        required=bool(expected_refs))

    opening_refs = [entry for entry in expected_refs
                    if re.search(r"opening|first", entry["role"], re.I)]
    opening_ok = True
    if opening_refs:
        for entry in opening_refs:
            matching = [line for line, keys in line_refs if entry["key"] in keys]
            if not any(re.search(r"\b(first|opening|begin|starts?)\b", line, re.I)
                       for line in matching):
                opening_ok = False
    add(
        "opening-frame", "Opening-frame authority", opening_ok,
        ("The opening reference explicitly controls the first visible state."
         if opening_ok else "The opening reference is present but is not assigned first-frame authority."),
        "State which reference is the first frame and what composition, pose and prop state it controls.",
        required=bool(opening_refs), authority="studio-policy")

    global_supplement = ""
    stage_matches = []
    if task_mode in staged_generation_modes:
        global_settings, global_heading = _first_section_body(
            text, ("Global Settings", "Global Scene Setting", "Global Setting"))
        add(
            "global-settings", "Global world and anti-collapse settings",
            bool(global_settings),
            (f"[{global_heading}] establishes the world, look and camera language."
             if global_settings else
             "No explicit global environment, visual style and camera-language section was found."),
            "Add [Global Settings] covering environment, visual style, "
            "camera language, character styling, performance core and prohibited items.",
            required=task_mode in {"thirty-second-video", "ultra-long-video"})

        shot_sequence = (
            _section_body(text, "Shot Sequence")
            or _section_body(text, "Camera and Shot Plan"))
        shot_numbers = [int(value) for value in re.findall(
            r"(?im)^\s*Shot\s+(\d+)\s*:", shot_sequence)]
        multi_shot = bool(shot_sequence and shot_numbers)
        if multi_shot:
            numbered = shot_numbers == list(range(1, len(shot_numbers) + 1))
            shot_lines = re.findall(r"(?im)^\s*Shot\s+\d+\s*:.*$", shot_sequence)
            directed = bool(shot_lines) and all(
                re.search(r"\bCamera\s*:", line, re.I) and
                re.search(r"\bAction\s*:", line, re.I) and
                re.search(r"\bEnd state\s*:", line, re.I)
                for line in shot_lines)
            add("stages", "Consecutive directed shots", numbered,
                f"{len(shot_numbers)} consecutive shot(s) carry the event progression.",
                "Use consecutive Shot N lines inside [Shot Sequence].")
            add("approved-stage-plan", "Approved story plan", True,
                "The typed approved stage plan remains the compiler source behind the shot sequence.",
                "Restore the typed story plan before compiling.",
                required=bool(stage_plan), authority="studio-policy")
            add("stage-direction", "Action and performance direction", directed,
                "Every internal shot has one camera job, action and visible end state." if directed else
                "At least one internal shot lacks camera, action or visible end state.",
                "Give each Shot N one Camera, Action and End state.")
            add("stage-end-states", "Visible shot handoffs", directed,
                "Every internal shot ends on a visible handoff." if directed else
                "At least one internal shot lacks a directly visible end state.",
                "Add End state to every Shot N.", authority="studio-policy")
            stage_matches = []
        else:
            stage_matches = _stage_matches(text)
        stage_numbers = [_stage_number(match) for match in stage_matches]
        stage_blocks = _stage_blocks(text, stage_matches)
        expected_stage_count = len(stage_plan or [])
        if not multi_shot:
            numbered = bool(stage_numbers) and stage_numbers == list(range(1, len(stage_numbers) + 1))
            add(
                "stages", "Consecutive storyboard stages", numbered,
                (f"{len(stage_numbers)} consecutive stage(s) carry the event progression."
                 if numbered else f"Found stages {stage_numbers or 'none'}, not a 1..N sequence."),
                "Use consecutive [Stage N] headings or official 'Stage N: 0-3s [Phase]' headings.")
            add(
                "approved-stage-plan", "Approved stage count",
                not expected_stage_count or len(stage_numbers) == expected_stage_count,
                (f"The prompt carries all {expected_stage_count} approved stage(s)."
                 if expected_stage_count and len(stage_numbers) == expected_stage_count else
                 "No typed approved stage plan was supplied to this check."
                 if not expected_stage_count else
                 f"The prompt has {len(stage_numbers)} stage(s), but the approved plan has "
                 f"{expected_stage_count}."),
                "Restore the exact number and order of approved stages before approval.",
                required=bool(expected_stage_count), authority="studio-policy")
            directed_stages = bool(stage_blocks) and all(
                len(re.findall(
                    r"(?im)^\s*(?:Primary event|Action\s*/\s*Expression)\s*:", block)) == 1 and
                (bool(re.search(r"(?im)^\s*Primary event\s*:", block)) or
                 bool(re.search(
                     r"(?im)^\s*(?:Emotion(?:al)? Analysis|Emotion\s*/\s*Camera Analysis|"
                     r"Camera Scheduling|Camera Analysis)\s*:", block)))
                for block in stage_blocks)
            add(
                "stage-direction", "Action and performance direction", directed_stages,
                ("Every stage has one primary action/expression plus emotional or camera direction."
                 if directed_stages else
                 "At least one stage lacks a single action/expression or its emotional/camera purpose."),
                "Give each official stage one Action/Expression and one Emotion/Camera Analysis; "
                "the legacy Primary event label remains accepted.")
            studio_stage_shape = bool(stage_blocks) and all(
                bool(re.search(r"(?im)^\s*(?:Initial state|Continue from the previous stage)\s*:", block)) and
                bool(re.search(r"(?im)^\s*End state\s*:", block))
                for block in stage_blocks)
            add(
                "stage-end-states", "Inherited state and visible handoff", studio_stage_shape,
                ("Every stage begins from an inherited state and ends on an observable handoff."
                 if studio_stage_shape else
                 "At least one stage lacks its inherited start or directly visible end state."),
                "Add Initial state (or Continue from the previous stage) and End state to every stage.",
                authority="studio-policy")
        global_supplement, supplement_heading = _first_section_body(
            text, ("Global Supplement", "Overall Supplement", "Maintain Consistency"))
        consistency_ok = bool(global_supplement and re.search(
            r"\b(keep|maintain|preserve|remain|throughout|must)\b", global_supplement, re.I))
        add(
            "consistency", "Global continuity supplement", consistency_ok,
            (f"[{supplement_heading}] protects identity, ownership and screen geography."
             if consistency_ok else "No actionable global supplement was found."),
            "End with [Global Supplement] or [Maintain Consistency] covering identity, count, "
            "prop ownership, axis, lighting and sound relationships.")
    elif task_mode == "first-last-frame":
        first_ok = bool(re.search(
            r"@(?:Image|\u56fe)\s*\d+.*\bis the first frame\b", text, re.I))
        last_ok = bool(re.search(
            r"@(?:Image|\u56fe)\s*\d+.*\bis the last frame\b", text, re.I))
        add("first-frame-role", "First-frame authority", first_ok,
            "The opening anchor is explicitly assigned." if first_ok else
            "No image is explicitly assigned as the first frame.",
            "Assign one image as the first frame and state the composition, pose, props and camera it controls.")
        add("last-frame-role", "Last-frame authority", last_ok,
            "The closing anchor is explicitly assigned." if last_ok else
            "No image is explicitly assigned as the last frame.",
            "Assign one image as the last frame and state the composition, pose, props and camera it controls.")
        action_body = _section_body(text, "Continuous Action")
        add("continuous-action", "Continuous journey", bool(action_body),
            "A continuous event connects both anchors." if action_body else
            "No continuous action between the anchors is defined.",
            "Add [Continuous Action] with one playable event that begins at the first frame and reaches the last.")
        global_supplement, supplement_heading = _first_section_body(
            text, ("Maintain Consistency", "Global Supplement"))
        consistency_ok = bool(global_supplement and re.search(
            r"\b(keep|maintain|preserve|remain|throughout|must)\b", global_supplement, re.I))
        add("consistency", "Between-anchor continuity", consistency_ok,
            f"[{supplement_heading}] protects continuity between the anchors."
            if consistency_ok else "No actionable between-anchor consistency contract was found.",
            "Protect identity, prop ownership, scene layout, lighting and camera direction between both anchors.")
    elif task_mode == "storyboard-grid":
        storyboard_body = _section_body(text, "Storyboard Role")
        storyboard_ok = bool(storyboard_body and re.search(r"\bstoryboard grid\b", storyboard_body, re.I))
        order_ok = bool(storyboard_body and re.search(
            r"\b(?:left to right|right to left|top to bottom|reading order)\b", storyboard_body, re.I))
        shot_count = len(re.findall(r"(?im)^\s*Shot\s+\d+\s*:", text))
        add("storyboard-role", "Storyboard-grid role", storyboard_ok,
            "The grid controls shot order and approximate composition." if storyboard_ok else
            "No storyboard grid is assigned a bounded role.",
            "Assign one image as the storyboard grid and exclude its line art, labels and placeholders.")
        add("storyboard-order", "Storyboard reading order", order_ok,
            "The grid has an explicit reading order." if order_ok else
            "The grid reading order is missing.",
            "State the exact panel reading order.")
        add("storyboard-shots", "Per-panel shot plan", shot_count > 0,
            f"{shot_count} storyboard shot(s) are directed." if shot_count else
            "No per-panel shot descriptions were found.",
            "Add one Shot N line per intended panel with framing, action and end state.")
        global_supplement, _ = _first_section_body(
            text, ("Maintain Consistency", "Global Supplement"))
    elif task_mode == "blockout-render":
        blockout_body = _section_body(text, "Blockout Role")
        type_ok = bool(blockout_body and re.search(r"\b(?:coarse|fine) blockout\b", blockout_body, re.I))
        preserve_ok = bool(blockout_body and re.search(r"\bpreserve only\b", blockout_body, re.I))
        exclude_ok = bool(blockout_body and re.search(
            r"\b(?:do not use|no)\b.*\b(?:gray|blockout|production markers?|path lines?|controllers?)\b",
            blockout_body, re.I | re.S))
        mapping_ok = bool(re.search(
            r"(?im)^.*(?:corresponds? to|maps? to|replace .* with).*$", text))
        add("blockout-type", "Blockout type", type_ok,
            "The source is classified as coarse or fine." if type_ok else
            "The blockout is not classified as coarse or fine.",
            "Classify the source as a coarse motion skeleton or a fine structural render.")
        add("blockout-inheritance", "Blockout inheritance", preserve_ok,
            "Only named temporal or structural attributes are inherited." if preserve_ok else
            "The exact blockout attributes to inherit are not bounded.",
            "State exactly which motion, blocking, camera, cuts, structure or spatial relationships to preserve.")
        add("blockout-exclusions", "Production-marker exclusions", exclude_ok,
            "Gray materials and production markers are excluded." if exclude_ok else
            "Blockout appearance or production markers are not explicitly excluded.",
            "Exclude gray materials, path lines, axes, controllers and camera cones.")
        add("blockout-mapping", "Blockout subject mapping", mapping_ok,
            "Blockout subjects are mapped to final subjects." if mapping_ok else
            "No blockout primitive-to-subject mapping was found.",
            "Map each primitive or blockout subject to one named final subject.")
        global_supplement, _ = _first_section_body(
            text, ("Maintain Consistency", "Global Supplement"))
    elif task_mode == "video-edit":
        add("editing-master", "Sole editing master",
            bool(re.search(r"@Video\s*1.*\bsole editing master\b", text, re.I | re.S)),
            "The source video must own characters, action, camera, timing and event order.",
            "Declare @Video 1 as the sole editing master and list what it controls.")
        for code, label, heading in (
                ("edit-scope", "Edit scope", "Edit Scope"),
                ("preserve", "Content to preserve", "Content to Preserve")):
            body = _section_body(text, heading)
            add(code, label, bool(body),
                f"[{heading}] is populated." if body else f"[{heading}] is missing or empty.",
                f"Add [{heading}] and name the exact region, time, object or content relationship.")
    elif task_mode in {"extend-forward", "extend-backward"}:
        forward = task_mode == "extend-forward"
        boundary = (r"first frame.*continues?.*last frame" if forward else
                    r"last frame.*connects?.*first frame")
        add("extension-master", "Extension source", bool(re.search(
            r"@Video\s*1.*\bsource video\b", text, re.I | re.S)),
            "@Video 1 must control the extension boundary.",
            "Declare @Video 1 as the source video to extend.")
        add("boundary-frame", "Boundary-frame continuity", bool(re.search(
            boundary, text, re.I | re.S)),
            "The extension must describe the exact source boundary it continues.",
            "Describe pose, props, layout, camera, light and motion at the connecting frame.")
        add("continuous-instance", "Stable subject instances", bool(re.search(
            r"\b(do not duplicate|same continuous instance|do not split)\b", text, re.I)),
            "Subject count and identity must remain stable through the extension.",
            "State that each subject remains the same continuous instance without duplication or splitting.")
    else:
        transition_checks = (
            ("transition-sources", "Before and after videos",
             r"@Video\s*1.*(?:before-transition|before transition).*@Video\s*2.*(?:after-transition|after transition)",
             "Assign @Video 1 as before-transition and @Video 2 as after-transition."),
            ("transition-trigger", "Transition trigger", r"\btriggers? the transition\b",
             "Name the action or occluding object that triggers the transition."),
            ("transition-arrival", "Arrival state", r"\btransition ends?\b.*\b(opening|composition|state)\b",
             "Describe the exact opening composition and motion trend reached in @Video 2."),
            ("transition-audio", "Audio transition", r"\b(audio|music|ambience|sound).*\b(fades?|transitions?|becomes?)\b",
             "Describe how the before audio becomes the after audio."),
        )
        for code, label, pattern, action in transition_checks:
            ok = bool(re.search(pattern, text, re.I | re.S))
            add(code, label, ok, f"{label} is explicit." if ok else f"{label} is not explicit.", action)

    audio_body = _section_body(text, "Audio")
    if dialogue_lines:
        speakers = {str((line or {}).get("speaker") or "").strip().lower()
                    for line in dialogue_lines}
        speakers.discard("")
        first_line = lines[0] if lines else ""
        synthesis = emission.validate_dialogue_synthesis(text, dialogue_lines)
        audio_ok = bool(
            "audio:1" in used_refs and synthesis["ready"] and
            all(speaker in text.lower() for speaker in speakers) and
            (audio_body or re.search(r"\b(audio|voice|dialogue)\b", global_supplement, re.I)))
        audio_detail = (
            "The prompt places each locked line once and gives @Audio1 sole performance authority."
            if audio_ok else
            "The dialogue synthesis contract is incomplete: " +
            "; ".join(synthesis["errors"]))
        add("audio", "Dialogue and audio authority", audio_ok, audio_detail,
            "Place each exact line once in braces, bind every speaker to @Audio1 as sole "
            "performance authority, and keep listeners silent.", authority="studio-policy")
    else:
        audio_scope = audio_body or global_supplement
        audio_ok = bool(audio_scope and re.search(
            r"\b(no dialogue|silent|ambience|sound|audio|music|bgm)\b", audio_scope, re.I))
        add("audio", "Dialogue and audio authority", audio_ok,
            "The prompt records silence, ambience or sound ownership."
            if audio_ok else "No section records silence, ambience or sound ownership.",
            "Record audio ownership in [Audio] or the [Global Supplement], even for a silent shot.",
            authority="studio-policy")

    pacing_text = ("\n".join(match.group(0) for match in stage_matches)
                   if task_mode in staged_generation_modes else text)
    ranges = [(_time_value(start), _time_value(end))
              for start, end in _TIME_RANGE.findall(pacing_text)]
    ranges_ok = all(start < end for start, end in ranges)
    if len(ranges) > 1:
        ranges_ok = ranges_ok and all(
            -0.001 <= ranges[index][0] - ranges[index - 1][1] <= 1.001
            for index in range(1, len(ranges)))
    if ranges and duration_value is not None:
        ranges_ok = (ranges_ok and ranges[0][0] <= 1.001 and
                     abs(ranges[-1][1] - duration_value) <= 1.001)
    pacing_ok = ranges_ok and (bool(ranges) or not timestamp_required)
    add("pacing", "Pacing control", pacing_ok,
        ("Storyline stages control pacing; timestamps are optional unless a critical "
         "handoff, entrance, exit, transition or dialogue cue needs timing."
         if not ranges else
         f"{len(ranges)} time range(s) are consecutive and non-overlapping." if ranges_ok else
         "Time ranges overlap, leave gaps or run backwards."),
        "Use consecutive [Stage N] sections with one primary change and visible end state; "
        "add time ranges only where critical timing needs protection.")

    parameter_hits = sorted(set(match.group(0) for match in _REQUEST_PARAMETER_WORDS.finditer(text)))
    add("request-parameters", "Request parameters stay outside the prompt", not parameter_hits,
        ("Duration, aspect ratio, resolution and model selection remain in the API contract."
         if not parameter_hits else "Prompt includes request parameters: " + ", ".join(parameter_hits)),
        "Remove generation duration, aspect ratio, resolution and model selection from the prompt.",
        authority="studio-policy")

    duration_ok = duration_sec is None
    duration_detail = "Duration was not supplied to this authoring check."
    if duration_sec is not None:
        if duration_numeric:
            if task_mode == "ultra-long-video":
                duration_ok = 30 <= duration_value <= 180
                duration_detail = (
                    f"{duration_value:g}s is within the Dreamina 30-180 second Ultra-Long authoring window."
                    if duration_ok else
                    f"{duration_value:g}s is outside the Dreamina 30-180 second Ultra-Long authoring window.")
            elif task_mode in {"extend-forward", "extend-backward"}:
                duration_ok = 4 <= duration_value <= 30
                duration_detail = (
                    f"{duration_value:g}s is within the official 4-30 second extension-pass window."
                    if duration_ok else
                    f"{duration_value:g}s is outside the official 4-30 second extension-pass window.")
            else:
                duration_ok = 4 <= duration_value <= 30
                duration_detail = (f"{duration_value:g}s is within the official 4-30 second standard window."
                                   if duration_ok else
                                   f"{duration_value:g}s is outside the official 4-30 second standard window.")
        else:
            duration_ok = False
            duration_detail = "Duration is not numeric."
    add("guide-duration", "Guide duration", duration_ok, duration_detail,
        "Keep a standard generation or extension unit between 4 and 30 seconds; Ultra-Long "
        "is a separate 30-180 second Dreamina authoring mode and is not an enabled API route.",
        required=duration_sec is not None)

    required_checks = [check for check in checks if check["required"]]
    passed = sum(check["status"] == "pass" for check in required_checks)
    repair_actions = []
    for check in required_checks:
        action = check.get("nextAction")
        if check["status"] != "pass" and action and action not in repair_actions:
            repair_actions.append(action)
    status = "ready" if passed == len(required_checks) else "needs-work"
    authority_scores = {}
    for authority, label in (("official-guide", "Official guide"),
                             ("studio-policy", "Studio production policy")):
        owned = [check for check in required_checks if check["authority"] == authority]
        authority_scores[authority] = {
            "label": label,
            "score": sum(check["status"] == "pass" for check in owned),
            "maximum": len(owned),
        }
    return {
        "profile": SEEDANCE_GUIDE_PROFILE,
        "source": dict(SEEDANCE_GUIDE_SOURCE),
        "guideLimits": dict(SEEDANCE_GUIDE_LIMITS),
        "guideSemantics": dict(SEEDANCE_GUIDE_SEMANTICS),
        "taskMode": task_mode,
        "status": status,
        "score": passed,
        "maximum": len(required_checks),
        "authorityScores": authority_scores,
        "summary": ("Prompt matches every required authoring check."
                    if status == "ready" else
                    f"{len(required_checks) - passed} authoring repair(s) remain before approval."),
        "referenceCount": len(expected_refs),
        "referenceCounts": reference_counts,
        "stageCount": len(stage_matches),
        "checks": checks,
        "repairActions": repair_actions,
        "advisoryOnly": True,
        "providerAvailabilityChecked": False,
        "providerCalled": False,
    }


def dimensions_for(artifact_type):
    if artifact_type not in VALID_ARTIFACT_TYPES:
        raise ValueError("artifactType must be keyframe or animation")
    return KEYFRAME_DIMENSIONS if artifact_type == "keyframe" else ANIMATION_DIMENSIONS


def classify_feedback(note):
    """Tag a human note without turning it into an invented numeric judgment."""
    text = str(note or "").strip()
    return [name for name, pattern in _FEEDBACK_PATTERNS.items() if pattern.search(text)]


def _source_value(source, path):
    value = source
    for name in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(name)
    if isinstance(value, (dict, list)):
        return ""
    return str(value or "").strip()


def _source_label(path):
    name = path[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).replace("Prose", "").strip().title()


def _correlation_tokens(text):
    return {
        token for token in re.findall(r"[a-z0-9']+", str(text or "").lower())
        if len(token) >= 4 and token not in _CORRELATION_STOPWORDS
    }


def _prompt_evidence(analysis, prompt_tags, wish_text, match_terms=()):
    """Locate exact prompt clauses by declared craft tags and lexical overlap."""
    wish_tokens = _correlation_tokens(" ".join(match_terms)) or _correlation_tokens(wish_text)
    ranked = []
    for clause in (analysis or {}).get("clauses") or []:
        matched_tags = sorted(set(clause.get("tags") or []) & set(prompt_tags))
        if not matched_tags:
            continue
        shared = sorted(wish_tokens & _correlation_tokens(clause.get("text")))
        ranked.append((
            min(len(shared), 20) * 100 + len(matched_tags) * 10,
            -int(clause.get("index") or 0),
            {
                "index": clause.get("index"),
                "text": clause.get("text"),
                "matchedTags": matched_tags,
                "sharedTerms": shared[:8],
            },
        ))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    evidence = [item[2] for item in ranked if item[2]["sharedTerms"]][:2]
    if not evidence and ranked:
        evidence = [ranked[0][2]]
    return {
        "status": ("located" if evidence and evidence[0]["sharedTerms"] else
                   "tag-only" if evidence else "not-located"),
        "clauses": evidence,
        "semanticClaim": False,
    }


def _selected_approval(ledger, artifact_type, selected):
    if not selected or selected.get("state") != "approved":
        return None
    if artifact_type == "keyframe":
        approval = ledger.get("keyframeApproval") or {}
        reviewer = approval.get("reviewedBy") or approval.get("reviewed_by")
        created_at = approval.get("approvedAt") or approval.get("at")
        if not (reviewer or created_at or approval.get("path")):
            return None
        return {"approved": True, "reviewer": reviewer, "createdAt": created_at}
    approval = ledger.get("approval") or {}
    match = re.fullmatch(r"C(\d+)", str(selected.get("candidateId") or ""))
    if not approval.get("approved") or not match:
        return None
    if int(approval.get("candidate") or 0) != int(match.group(1)):
        return None
    return {
        "approved": True,
        "reviewer": approval.get("reviewed_by") or approval.get("reviewedBy"),
        "createdAt": approval.get("at") or approval.get("approvedAt"),
    }


def build_direction_correlation(shot, analysis, artifact_type, *, selected=None,
                                ledger=None, feedback=None, ratings=None,
                                current_asset_hash=None,
                                prompt_applies_to_render=False,
                                prompt_plan_summary=""):
    """Build a non-generative director -> prompt -> outcome trace.

    Outcome comments are included only when their batch or candidate identifier matches
    the selected media. Older comments remain visible as prior attempts, never as evidence
    for the current take.
    """
    if artifact_type not in VALID_ARTIFACT_TYPES:
        raise ValueError("artifactType must be keyframe or animation")
    ledger = ledger or {}
    feedback = list(feedback or [])
    ratings = list(ratings or [])
    selected = selected or None
    selected_candidate = str((selected or {}).get("candidateId") or "")
    selected_contract = (selected or {}).get("promptContract") or {}
    selected_batch = str(selected_contract.get("batchId") or "")

    def feedback_matches(item):
        candidate_match = bool(
            selected_candidate and item.get("candidateId") == selected_candidate)
        batch_match = bool(selected_batch and item.get("batchId") == selected_batch)
        return candidate_match or batch_match

    linked_feedback = [item for item in feedback if feedback_matches(item)]
    prior_feedback = [
        item for item in feedback
        if item.get("kind") == "render-comment" and not feedback_matches(item)
    ]
    selected_ratings = [
        item for item in ratings
        if selected_candidate and item.get("candidateId") == selected_candidate
        and current_asset_hash and item.get("assetHash") == current_asset_hash
    ]
    selected_ratings.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    latest_rating = selected_ratings[0] if selected_ratings else None
    approval = _selected_approval(ledger, artifact_type, selected)

    rows = []
    for axis in _CORRELATION_AXES[artifact_type]:
        sources = []
        for path in axis["sources"]:
            value = _source_value(shot, path)
            if value:
                sources.append({
                    "field": ".".join(path),
                    "label": _source_label(path),
                    "text": value,
                })
        wish_text = " ".join(item["text"] for item in sources)
        prompt_evidence = _prompt_evidence(
            analysis, axis["promptTags"], wish_text, axis.get("matchTerms") or ())
        if not prompt_applies_to_render:
            prompt_evidence["status"] = "direction-only"

        relevant_feedback = [
            item for item in linked_feedback
            if set(item.get("topics") or []) & set(axis["feedbackTopics"])
        ]
        score = None
        if latest_rating:
            score = (latest_rating.get("scores") or {}).get(axis["ratingDimension"])
        if isinstance(score, int):
            outcome_status = {0: "miss", 1: "partial", 2: "lands"}.get(score, "rated")
        elif relevant_feedback:
            outcome_status = "commented"
        else:
            outcome_status = "not-rated"
        rows.append({
            "key": axis["key"],
            "label": axis["label"],
            "directorWish": {
                "status": "recorded" if sources else "not-recorded",
                "sources": sources,
            },
            "promptInstruction": prompt_evidence,
            "observedResult": {
                "status": outcome_status,
                "score": score,
                "maximum": 2 if isinstance(score, int) else None,
                "ratingDimension": axis["ratingDimension"],
                "ratingId": (latest_rating or {}).get("ratingId"),
                "reviewer": (latest_rating or {}).get("reviewer"),
                "createdAt": (latest_rating or {}).get("createdAt"),
                "ratingNote": (latest_rating or {}).get("note"),
                "comments": relevant_feedback,
                "scoreInferredFromComment": False,
            },
        })

    if selected_ratings:
        outcome_status = "rated"
        summary = "The selected media has a human rating tied to its current bytes."
    elif linked_feedback:
        outcome_status = "commented"
        summary = "A written result is linked to this selected batch or candidate."
    elif approval:
        outcome_status = "approved-unrated"
        summary = (
            "Approval is recorded, but no written per-aspect outcome is tied to this take yet."
        )
    elif selected:
        outcome_status = "not-recorded"
        summary = "No human result is tied to this selected take yet."
    else:
        outcome_status = "no-render"
        summary = "Direction and prompt can be compared, but there is no selected render."

    if selected and selected.get("attributionExact"):
        asset_binding = "generation-hash"
    elif selected:
        asset_binding = "surviving-media-only"
    else:
        asset_binding = "no-media"
    if selected and selected.get("promptAttributionExact") and prompt_applies_to_render:
        prompt_binding = "sealed-batch-prompt"
    elif prompt_applies_to_render:
        prompt_binding = "recorded-prompt"
    else:
        prompt_binding = "current-direction-only"

    director_text = str(
        shot.get("purpose") or shot.get("feltIntent") or shot.get("visualPayoff") or ""
    ).strip()
    supporting_text = str(
        shot.get("visualPayoff") or shot.get("feltIntent") or ""
    ).strip()
    latest_rating_public = None
    if latest_rating:
        latest_rating_public = {
            "ratingId": latest_rating.get("ratingId"),
            "overallRead": latest_rating.get("overallRead"),
            "note": latest_rating.get("note"),
            "reviewer": latest_rating.get("reviewer"),
            "createdAt": latest_rating.get("createdAt"),
            "detailed": bool(latest_rating.get("scores")),
        }

    return {
        "scope": {
            "candidateId": selected_candidate or None,
            "batchId": selected_batch or None,
            "state": (selected or {}).get("state"),
            "promptBinding": prompt_binding,
            "assetBinding": asset_binding,
            "outcomeBinding": outcome_status,
        },
        "summary": summary,
        "approval": approval,
        "creativeLoop": {
            "directorWants": {
                "text": director_text,
                "supportingText": supporting_text if supporting_text != director_text else "",
                "sourceField": ("purpose" if shot.get("purpose") else
                                "feltIntent" if shot.get("feltIntent") else
                                "visualPayoff" if shot.get("visualPayoff") else None),
            },
            "promptBuiltToDeliver": {
                "text": str(prompt_plan_summary or "").strip(),
                "binding": prompt_binding,
                "source": "approved-specialist-delivery-plan" if prompt_plan_summary else None,
            },
            "whatHappened": {
                "status": outcome_status,
                "summary": summary,
                "latestRating": latest_rating_public,
                "comments": linked_feedback,
            },
        },
        "rows": rows,
        "linkedComments": linked_feedback,
        "linkedRatingCount": len(selected_ratings),
        "priorAttempts": prior_feedback,
        "causalClaim": False,
    }


def _dimension(score, evidence, applicable=True):
    return {
        "score": int(score) if applicable else None,
        "maximum": 2 if applicable else None,
        "applicable": bool(applicable),
        "evidence": list(evidence),
    }


def analyze_prompt(prompt, artifact_type, dialogue_lines=None):
    """Return reproducible structural evidence for one exact provider prompt."""
    if artifact_type not in VALID_ARTIFACT_TYPES:
        raise ValueError("artifactType must be keyframe or animation")
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("prompt cannot be blank")

    sentences = _sentences(text)
    clauses = []
    category_counts = {name: 0 for name in _CATEGORY_PATTERNS}
    for index, sentence in enumerate(sentences, start=1):
        tags = [name for name, pattern in _CATEGORY_PATTERNS.items()
                if pattern.search(sentence)]
        for tag in tags:
            category_counts[tag] += 1
        clauses.append({
            "index": index,
            "text": sentence,
            "wordCount": len(sentence.split()),
            "tags": tags,
        })

    def evidence(*categories):
        return [item["index"] for item in clauses
                if any(category in item["tags"] for category in categories)]

    has = lambda category: bool(category_counts.get(category))
    opening = bool(re.search(r"\b(opening frame|first frame|starts? on|begins? on)\b", text, re.I))
    landing = bool(re.search(r"\b(landing image|lands? on|ends? on|final frame|closing frame|handoff)\b", text, re.I))
    identity_evidence = evidence("identity")
    composition_evidence = evidence("composition")
    look_evidence = evidence("look")

    dimensions = OrderedDict()
    dimensions["beatDelivery"] = _dimension(
        2 if has("intent") and (has("performance") or has("action")) else
        1 if has("intent") or has("action") else 0,
        evidence("intent", "action"))
    dimensions["actingAndPerformance"] = _dimension(
        2 if has("performance") and has("timing") else 1 if has("performance") else 0,
        evidence("performance", "timing"))
    dimensions["physicalCausality"] = _dimension(
        2 if has("action") and has("causality") else 1 if has("action") else 0,
        evidence("action", "causality"), artifact_type == "animation")
    dimensions["timingAndReaction"] = _dimension(
        2 if has("timing") and has("performance") else 1 if has("timing") else 0,
        evidence("timing", "performance"), artifact_type == "animation")
    dimensions["cameraAndEdit"] = _dimension(
        2 if has("camera") and has("composition") else
        1 if has("camera") or has("composition") else 0,
        evidence("camera", "composition"))
    dimensions["compositionAndContinuity"] = _dimension(
        2 if composition_evidence and (landing if artifact_type == "animation" else opening)
        else 1 if composition_evidence or opening or landing else 0,
        sorted(set(composition_evidence + evidence("continuity"))))
    dimensions["identityAndReferenceUse"] = _dimension(
        2 if identity_evidence and re.search(r"@图\d+", text, re.I)
        else 1 if identity_evidence else 0,
        identity_evidence)
    dimensions["finishAndProductionValue"] = _dimension(
        2 if look_evidence and composition_evidence else 1 if look_evidence else 0,
        sorted(set(look_evidence + composition_evidence)))

    warnings = []
    word_count = len(text.split())
    minimum = 24 if artifact_type == "keyframe" else 40
    maximum = 240 if artifact_type == "keyframe" else 360
    if word_count < minimum:
        warnings.append({"code": "thin-direction", "message":
                         f"Only {word_count} words; observable direction may be underspecified."})
    if word_count > maximum:
        warnings.append({"code": "prompt-density", "message":
                         f"{word_count} words; competing instructions may dilute the main beat."})
    overloaded = [item["index"] for item in clauses if item["wordCount"] > 55]
    if overloaded:
        warnings.append({"code": "overloaded-clause", "message":
                         "Long clauses may hide instruction priority.", "clauses": overloaded})

    seen = {}
    for item in clauses:
        key = _normalise(item["text"])
        seen.setdefault(key, []).append(item["index"])
    duplicate_groups = [indexes for indexes in seen.values() if len(indexes) > 1]
    if duplicate_groups:
        warnings.append({"code": "duplicate-direction", "message":
                         "Repeated direction spends prompt attention without adding control.",
                         "clauses": [index for group in duplicate_groups for index in group]})
    if _CAMERA_LOCK.search(text) and _CAMERA_MOVE.search(text):
        warnings.append({"code": "camera-conflict", "message":
                         "Locked and moving camera instructions both appear."})

    negative_count = len(_NEGATIVE.findall(text))
    if negative_count >= 7:
        warnings.append({"code": "negative-density", "message":
                         f"{negative_count} negative constraints may compete with positive action direction."})
    generic_count = len(_GENERIC_POLISH.findall(text))
    if generic_count >= 3 and not (has("camera") and has("look")):
        warnings.append({"code": "generic-polish", "message":
                         "Polish adjectives are not backed by enough concrete camera or material direction."})
    if artifact_type == "animation" and not opening:
        warnings.append({"code": "missing-opening", "message":
                         "No explicit opening-frame instruction was detected."})
    if artifact_type == "animation" and not landing:
        warnings.append({"code": "missing-landing", "message":
                         "No explicit final landing or handoff was detected."})

    synthesis = emission.validate_dialogue_synthesis(text, dialogue_lines or [])
    if not synthesis["ready"]:
        warnings.append({"code": "dialogue-synthesis", "message":
                         "Dialogue placement or @Audio1 authority is incomplete.",
                         "errors": synthesis["errors"]})

    applicable = [item for item in dimensions.values() if item["applicable"]]
    score = sum(item["score"] for item in applicable)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": artifact_type,
        "promptHash": hashlib.sha256(text.encode()).hexdigest(),
        "wordCount": word_count,
        "sentenceCount": len(sentences),
        "score": score,
        "maximum": len(applicable) * 2,
        "dimensions": dimensions,
        "categoryCounts": category_counts,
        "features": {
            "hasOpening": opening,
            "hasLanding": landing,
            "negativeConstraintCount": negative_count,
            "genericPolishCount": generic_count,
            "overloadedClauseCount": len(overloaded),
            "duplicateDirectionGroups": len(duplicate_groups),
        },
        "clauses": clauses,
        "warnings": warnings,
        "advisoryOnly": True,
        "providerCalled": False,
    }


def validate_rating(artifact_type, scores, overall_read, note=""):
    expected = set(dimensions_for(artifact_type))
    supplied = set((scores or {}).keys())
    if supplied and supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        raise ValueError("rating dimensions do not match the artifact: " + "; ".join(detail))
    clean_scores = {}
    if supplied:
        for name in dimensions_for(artifact_type):
            value = scores[name]
            if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2):
                raise ValueError(f"{name} must be an integer score from 0 to 2")
            clean_scores[name] = value
    if overall_read not in VALID_OVERALL_READS:
        raise ValueError("overallRead must be miss, partial or lands")
    clean_note = str(note or "").strip()
    if len(clean_note) > 2000:
        raise ValueError("rating note must be 2000 characters or fewer")
    return clean_scores, overall_read, clean_note


def summarize_ratings(records, current_prompt_hash=None):
    """Summarise observed outcomes without making a causal prompt-quality claim."""
    records = list(records or [])
    learning_records = [
        item for item in records if item.get("learningEligible") is not False
    ]
    shots = {str(item.get("shotId")) for item in learning_records if item.get("shotId")}
    repeatable = len(learning_records) >= 3 and len(shots) >= 2
    dimensions = {}
    for name, label in DIMENSIONS.items():
        values = [item.get("scores", {}).get(name) for item in records]
        values = [value for value in values if isinstance(value, int)]
        if values:
            dimensions[name] = {
                "label": label,
                "count": len(values),
                "average": round(sum(values) / len(values), 2),
            }

    versions = {}
    for item in learning_records:
        prompt_hash = item.get("promptHash")
        values = list((item.get("scores") or {}).values())
        if not prompt_hash or not values:
            continue
        rec = versions.setdefault(prompt_hash, {"ratings": 0, "totals": [], "latestAt": None})
        rec["ratings"] += 1
        rec["totals"].append(sum(values) / len(values))
        rec["latestAt"] = max(rec["latestAt"] or "", item.get("createdAt") or "")
    version_rows = []
    for prompt_hash, values in versions.items():
        version_rows.append({
            "promptHash": prompt_hash,
            "current": prompt_hash == current_prompt_hash,
            "ratings": values["ratings"],
            "average": round(sum(values["totals"]) / len(values["totals"]), 2),
            "latestAt": values["latestAt"],
        })
    version_rows.sort(key=lambda item: item.get("latestAt") or "", reverse=True)

    current = next((item for item in version_rows if item["current"]), None)
    previous = next((item for item in version_rows if not item["current"]), None)
    comparison = None
    if current and previous:
        comparison = {
            "currentPromptHash": current["promptHash"],
            "previousPromptHash": previous["promptHash"],
            "currentAverage": current["average"],
            "previousAverage": previous["average"],
            "delta": round(current["average"] - previous["average"], 2),
            "causalClaim": False,
        }

    weakest = None
    if dimensions:
        name, value = min(dimensions.items(), key=lambda pair: pair[1]["average"])
        weakest = {"dimension": name, **value}
    return {
        "ratingCount": len(records),
        "promptLearningCount": len(learning_records),
        "qualityOnlyCount": len(records) - len(learning_records),
        "distinctShots": len(shots),
        "evidenceStatus": "repeatable-signal" if repeatable else "early-signal",
        "learningClaim": (
            "Repeated evidence is available; change one prompt lever and compare another exact render."
            if repeatable else
            "Not enough exact prompt/render evidence for a wording rule yet. Rate at least three "
            "eligible renders across two shots."
        ),
        "dimensionAverages": dimensions,
        "weakestObservedDimension": weakest,
        "promptVersions": version_rows,
        "versionComparison": comparison,
        "causalClaim": False,
    }
