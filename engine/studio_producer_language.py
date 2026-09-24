"""Translate every stop in the Golden Path into a producer sentence and one next action.

The producer sees images, dialogue and renders and decides approve / another version /
next. When the Studio stops, they must never see a compiler code, a hash or 'UNKNOWN'.
This is a read-only projection of the recorded technical cause; the raw text stays in the
journey record for production support. No provider, approval or state operation here.
"""
import re

# (pattern, category, headline, meaning, next action, button)
RULES = (
    (r"WATCH_SOURCE_PACKAGE_MISMATCH|SOURCE_DIALOGUE_SEGMENTATION_UNRESOLVED",
     'request',
     "Studio found a mismatch between the approved production pack and its source board.",
     "No media or approved work was changed. The current DIRECT, SEE and HEAR sources need to be recompiled as one WATCH request.",
     "Open WATCH and rebuild the request from the current approved pack; nothing is submitted until the sources agree.", "Open WATCH"),
    (r"opening-frame approval is stale|opening composition master is missing or stale",
     'images',
     "The approved opening frame no longer matches the current SEE inputs.",
     "The image is retained, but its approval was tied to an older direct input set.",
     "Open SEE, review the current scene plate and keyframe, then approve the current frame before WATCH.", "Review opening frame"),
    (r"WATCH_CONFIGURATION_REQUIRED.*(?:opening inputs changed|opening frame|opening keyframe).*(?:SEE|prior final frame|continuity)|opening frame is not a playable stage|opening geography does not provide visible depth|reserve lead room for travel",
     'images',
     "The opening frame needs a current continuity update.",
     "The saved image remains available, but its shot layout or prior-frame relationship needs another SEE review.",
     "Open SEE and use Library, Upload or Generate to update the opening frame, then review and approve it.", "Review opening frame"),
    (r"keyframe prompt.*\[SUBJECTS\].*approved DIRECT direction",
     'direction',
     "The keyframe prompt does not match approved shot direction.",
     "The character/subject wording in the keyframe brief did not preserve DIRECT's approved wording.",
     "Open DIRECT and align the subject direction, then return to SEE to build the keyframe.", "Review in DIRECT"),
    (r"WATCH_PROMPT_REVIEW_REQUIRED",
     'review',
     "The prompt reviewer couldn't verify its quotations.",
     "This is a review-format problem, not a failed media or timing check. Your approved opening and voice are retained.",
     "Open WATCH, inspect the cited evidence and correct its source. The request remains unsubmitted until you approve Fire.", "Review WATCH"),
    (r"DIRECT_AUDIO_TIMING_CONFLICT",
     'audio',
     "The spoken line and Sunny’s movement don’t line up yet.",
     "The approved voice finishes after the direction schedules the turn and garland grip. Studio has kept the voice and direction unchanged.",
     "Review the timed movement in DIRECT, or adjust the line timing in HEAR without changing its approved words. WATCH stays unsubmitted until the sources agree.", "Review timing in DIRECT"),
    (r"WATCH_AUTHORED_TIMED_ACTION_MISSING|Complete the timed action|Complete the authored timed action|DIRECT must author timed views",
     'direction',
     "This shot's direction isn't finished.",
     "The Director Card has no timed views yet, so Studio cannot film it.",
     "Open DIRECT, complete the timed views, then continue.", "Open direction"),
    (r"Director handoff incomplete.*(?:completion time|event time)|explicit event completion times",
     'direction',
     "The direction handoff needs event timing.",
     "The Director Card needs explicit event-completion times before later stages can use the shot.",
     "Open DIRECT and add the event completion times, then continue.", "Open direction"),
    (r"DIRECTOR_REVISION_REQUIRED|DIRECT_REVISION_REQUIRED",
     'direction',
     "The Director needs to revise this shot.",
     "Something in the direction is contradictory or incomplete.",
     "Open DIRECT, apply the noted revision, then continue.", "Open direction"),
    (r"HEAR_CONFIGURATION_REQUIRED.*(?:unoccupied|landing hold|acting and landing|voice ends|voice leaves)",
     'direction',
     "The spoken line leaves too little time for the shot's action and landing.",
     "Keep the approved dialogue; adjust the timed action or landing in DIRECT, or revise voice timing in HEAR.",
     "Open DIRECT to review the action timeline; HEAR remains available for a timing-only change.", "Review timing in DIRECT"),
    (r"HEAR_CONFIGURATION_REQUIRED|performance direction is missing",
     'audio',
     "A line has no voice direction.",
     "Every spoken line needs its performance direction before audio is created.",
     "Add the performance direction in DIRECT, then create the audio again.", "Open direction"),
    (r"WATCH_REFERENCE_MISSING|reference .* file is missing|reference file is missing",
     'references',
     "A reference image this shot needs can't be found.",
     "An approved image was moved or removed since it was reviewed.",
     "Re-select the image in SEE, then continue.", "Open images"),
    (r"WATCH_AUTHORED_ACTION_DRIFT|payload differs from current DIRECT compilation",
     'request',
     "The render request no longer matches the approved direction.",
     "The direction changed after the request was prepared.",
     "Open WATCH and prepare a fresh request from the current approved direction; nothing you approved is lost.", "Open WATCH"),
    (r"Approve the current WATCH request before firing",
     'request',
     "The render request needs approving before filming.",
     "Studio prepared the request; it needs your approval to spend.",
     "Review the sealed request and its cost in WATCH. No provider call occurs until you explicitly approve Fire.", "Review WATCH request"),
    (r"SPEND NOT APPROVED|spend envelope|allowance",
     'money',
     "This step costs money and hasn't been approved.",
     "The cost is shown before anything is charged.",
     "Review and approve the exact spend in WATCH before any provider request.", "Review spend in WATCH"),
    (r"credit_balance_exhausted|insufficient[_ ]credit|out of credit|quota",
     'provider',
     "The AI provider account is out of credit.",
     "Nothing here needs changing; the provider refused for lack of credit.",
     "No provider request can run until the account has available credit.", "View details"),
    (r"APITimeoutError|timed out|timeout",
     'provider',
     "The provider didn't answer in time.",
     "Studio does not charge for an unanswered request, but it checks before trying again.",
     "Try again; Studio will confirm nothing was charged.", "Try again"),
    (r"no current signed scene plate|SEE_SCENE_PLATE_AUTHORITY_STALE|scene plate",
     'images',
     "The scene's background plate needs approving first.",
     "Every scene is anchored on one approved world plate before its first image.",
     "Choose the plate from your library, upload one, or generate one, then approve it and continue.", "Open scene plate"),
    (r"BLOCKED: CHARACTER ROLE INTEGRITY|role swap|CHARACTER TRUTH",
     'direction',
     "Two characters could be confused in this shot.",
     "The direction or references don't make clear who does what.",
     "Open DIRECT and name who owns each action, then continue.", "Open direction"),
    (r"BLOCKED: STALE PACKAGE|STALE_DEPENDENCY|\bSTALE\b|has changed since|changed after your review|no longer matches",
     'stale',
     "Something this shot depends on changed since you reviewed it.",
     "An image, voice or direction was updated after the last review.",
     "Review the updated version, then continue.", "Review update"),
    (r"BLOCKED: PROVIDER PROMPT COMPILATION|BLOCKED: DIRECTION PLAN|WATCH_CONFIGURATION_REQUIRED",
     'direction',
     "Studio couldn't build the render request from the direction.",
     "The direction is missing something the render needs.",
     "Open DIRECT, complete what is noted, then prepare the request again.", "Open direction"),
    (r"Law 5|approved voice does not match",
     'audio',
     "The approved voice no longer matches the direction.",
     "The dialogue or its direction changed after the voice was recorded.",
     "Create the audio again, then continue.", "Create audio"),
    (r"production package failed design validation|failed validation",
     'direction',
     "The scene's production plan has an error.",
     "Studio refuses to film past a red validator.",
     "Open the scene plan, fix the noted error, then continue.", "Open scene"),
    (r"not registered|show profile is missing",
     'setup',
     "This production isn't set up in the Studio yet.",
     "The show's profile or project record is missing.",
     "Set the production up from Productions, then return here.", "Open productions"),
    (r"outside the Studio media library|escapes configured Studio roots|path escapes",
     'setup',
     "A file this shot needs is outside the Studio's folders.",
     "The Studio only uses files inside its own production folders.",
     "Review the blocked file path, then place the asset inside the configured Studio folder. Nothing you approved is lost.", "View file details"),
)


def _code(raw):
    match = re.search(r"\b([A-Z][A-Z0-9_]{6,})\b", str(raw))
    return match.group(1) if match else None


def _next_stage(category, stage, text):
    """Bind a producer stop to the stage that can actually resolve it."""
    if category == 'audio' and re.search(r'performance direction is missing|no voice direction', text, re.I):
        return 'direct'
    if category == 'audio' and re.search(r'DIRECT_AUDIO_TIMING_CONFLICT', text, re.I):
        return 'direct'
    if category == 'images':
        return 'see'
    if category == 'references':
        return 'see'
    if category == 'direction':
        return 'direct'
    if category in {'request', 'money', 'review'}:
        return 'watch'
    if category == 'audio':
        return 'hear'
    if category == 'stale':
        value = re.sub(r'[^a-z]+', '_', str(stage or '').lower()).strip('_')
        if any(part in value for part in ('see', 'image', 'keyframe', 'plate', 'look')):
            return 'see'
        if any(part in value for part in ('hear', 'audio', 'voice')):
            return 'hear'
        if any(part in value for part in ('watch', 'render', 'film', 'animation', 'request')):
            return 'watch'
        return 'direct'
    if category == 'provider':
        return 'recover' if re.search(r'Check existing job|timed out', text, re.I) else 'details'
    return 'details'


def translate(raw, *, stage=None):
    """Return the producer-facing reading of a recorded stop. Never raises."""
    text = str(raw or '').strip()
    for pattern, category, headline, meaning, action, button in RULES:
        if re.search(pattern, text, re.I):
            component = None
            if category == 'images':
                if re.search(r'opening[- ]frame|opening composition|opening inputs|keyframe', text, re.I):
                    component = 'opening'
                elif re.search(r'scene plate|background plate', text, re.I):
                    component = 'plate'
            return dict(category=category, headline=headline, meaning=meaning,
                        nextAction=action, button=button, code=_code(text), technical=text,
                        stage=stage, targetStage=_next_stage(category, stage, text),
                        component=component,
                        preserved="Everything you approved is saved.")
    return dict(category='support', headline='Studio stopped here and saved your approved work.',
                meaning='This stop is not one Studio can explain in plain words yet.',
                nextAction='Nothing you approved is lost. Open technical details to see the exact stop and the evidence needed to resolve it.',
                button='View technical details', code=_code(text), technical=text, stage=stage,
                targetStage='details', component=None,
                preserved="Everything you approved is saved.")


def stopped_message(raw, *, stage=None):
    """Headline plus next action, for the review card's single line."""
    p = translate(raw, stage=stage)
    return f"{p['headline']} {p['nextAction']}"
