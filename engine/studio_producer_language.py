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
     "Rebuild WATCH from the current approved pack; nothing is submitted until the sources agree.", "Rebuild WATCH"),
    (r"opening-frame approval is stale|opening composition master is missing or stale",
     'images',
     "The approved opening frame no longer matches the current SEE inputs.",
     "The image is retained, but its approval was tied to an older direct input set.",
     "Open SEE, review the current scene plate and keyframe, then approve the current frame before WATCH.", "Review opening frame"),
    (r"WATCH_PROMPT_REVIEW_REQUIRED",
     'direction',
     "The prompt reviewer couldn't verify its quotations.",
     "This is a review-format problem, not a failed media or timing check. Your approved opening and voice are retained.",
     "Retry the prompt review. Studio checks the exact request again; nothing is submitted until you approve Fire.", "Retry review"),
    (r"DIRECT_AUDIO_TIMING_CONFLICT",
     'audio',
     "The spoken line and Sunny’s movement don’t line up yet.",
     "The approved voice finishes after the direction schedules the turn and garland grip. Studio has kept the voice and direction unchanged.",
     "Choose whether to revise the movement in DIRECT or review the voice timing in HEAR. WATCH stays unsubmitted until the revised sources agree.", "Review timing options"),
    (r"immutable script content is missing|missing trusted show data|canon lock refused",
     'setup',
     "Required production source files are missing.",
     "The Studio cannot verify the saved script or locked show data.",
     "Restore the exact missing source files before continuing; do not regenerate media to repair them.", "Recover source files"),
    (r"typed opening-frame layout",
     'direction',
     "The opening-frame layout needs attention.",
     "SEE could not validate the opening cast, pose or layout.",
     "Review the opening composition in DIRECT, then prepare the keyframe again.", "Open direction"),
    (r"no current Director Review approval",
     'review',
     "The accepted film still needs its Director Review.",
     "The take is retained, but scene assembly requires a current review approval.",
     "Complete and approve the film's Director Review, then resume assembly.", "Review film"),
    (r"WATCH_AUTHORED_TIMED_ACTION_MISSING|Complete the timed action|Complete the authored timed action|DIRECT must author timed views",
     'direction',
     "This shot's direction isn't finished.",
     "The Director Card has no timed views yet, so Studio cannot film it.",
     "Open DIRECT, complete the timed views, then continue.", "Open direction"),
    (r"DIRECTOR_REVISION_REQUIRED|DIRECT_REVISION_REQUIRED",
     'direction',
     "The Director needs to revise this shot.",
     "Something in the direction is contradictory or incomplete.",
     "Open DIRECT, apply the noted revision, then continue.", "Open direction"),
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
     "Prepare the request again; nothing you approved is lost.", "Prepare again"),
    (r"Approve the current WATCH request before firing",
     'request',
     "The render request needs approving before filming.",
     "Studio prepared the request; it needs your approval to spend.",
     "Approve the request to film this shot.", "Approve and film"),
    (r"SPEND NOT APPROVED|spend envelope|allowance",
     'money',
     "This step costs money and hasn't been approved.",
     "The cost is shown before anything is charged.",
     "Approve the shown cost to continue.", "Approve spend"),
    (r"credit_balance_exhausted|insufficient[_ ]credit|out of credit|quota",
     'provider',
     "The AI provider account is out of credit.",
     "Nothing here needs changing; the provider refused for lack of credit.",
     "Top up the provider account, then continue.", "Try again"),
    (r"APITimeoutError|timed out|timeout",
     'provider',
     "The provider didn't answer in time.",
     "The provider may have accepted the request before the connection timed out.",
     "Check the existing provider job before retrying; do not submit a duplicate request.", "Check existing job"),
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
     'request',
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
     "Ask support to move the file into the Studio folder; nothing you approved is lost.", "Contact support"),
)


def _code(raw):
    match = re.search(r"\b([A-Z][A-Z0-9_]{6,})\b", str(raw))
    return match.group(1) if match else None


def translate(raw, *, stage=None):
    """Return the producer-facing reading of a recorded stop. Never raises."""
    text = str(raw or '').strip()
    for pattern, category, headline, meaning, action, button in RULES:
        if re.search(pattern, text, re.I):
            return dict(category=category, headline=headline, meaning=meaning,
                        nextAction=action, button=button, code=_code(text), technical=text,
                        stage=stage, preserved="Everything you approved is saved.")
    return dict(category='support', headline='Studio stopped here and saved your approved work.',
                meaning='This stop is not one Studio can explain in plain words yet.',
                nextAction='Nothing you approved is lost. Send the reference below to support.',
                button='Contact support', code=_code(text), technical=text, stage=stage,
                preserved="Everything you approved is saved.")


def stopped_message(raw, *, stage=None):
    """Headline plus next action, for the review card's single line."""
    p = translate(raw, stage=stage)
    return f"{p['headline']} {p['nextAction']}"
