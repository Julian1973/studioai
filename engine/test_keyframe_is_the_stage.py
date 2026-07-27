"""The keyframe is the STAGE, and it must be forgiving. Both halves bound."""
import inspect, cb_departments as D

def test_the_dp_writes_only_what_its_own_lens_can_see():
    """Julian, 2026-07-27, on the first keyframe fired after the ~170-word cap came off:
    "the image is awful... surely this shot is to narrow."

    The cap was deleted on real evidence — but all of it came from MOTION prompts, and rule
    87 flagged in the same breath that it "does not by itself prove a still-image cap wrong."
    A still and a take have OPPOSITE relationships with length. The cap had been quietly
    keeping the stage in the words; removing it let the performance move in, and the lens
    collapsed to a portrait to deliver detail no wide could ever show."""
    s = inspect.getsource(D.prepare_cinematography)
    assert "WRITE ONLY WHAT YOUR OWN LENS CAN ACTUALLY SEE" in s, (
        "the DP may describe eyelash detail at 24mm again — the render will abandon the wide "
        "to deliver it and Julian gets a portrait where he asked for a corridor")
    assert "SILHOUETTE" in s, "the wide-shot job (silhouette, attitude, position) is unstated"
    assert "PERFORMANCE IS NOT YOURS" in s, (
        "expression/mouth/antennae/wing-beat are no longer named as the performance's, so "
        "the still will keep trying to act")

def test_the_start_frame_is_forgiving():
    """Julian, 2026-07-27: "the keyframe is the stage the canvas for the animation to build
    on — it has to be the forgiving start frame." A frame pinned to one hyper-specific
    instant is a sculpture, and every frame after it reads as a departure from something the
    model was told to honour — the anti-hold failure (rules 26/31) arriving through the still
    instead of the text."""
    s = inspect.getsource(D.prepare_cinematography)
    assert "FORGIVING START FRAME" in s, "the canvas rule is gone — poses can be pinned again"
    assert "CANVAS, NOT A SCULPTURE" in s
    assert "EMPTY" in s, "the lane the action travels into is no longer protected"
    assert "without contradicting it" in s, (
        "the DP has no test to apply — 'could the first second of movement start here?' is "
        "the whole rule in one question")

def test_no_numeric_ceiling_came_back():
    """His standing law: name what to DELETE, never add a cap. The fix is a rule of KIND —
    it must not quietly become a rule of COUNT again."""
    s = inspect.getsource(D.prepare_cinematography)
    assert "there is no word ceiling here" in s, "a numeric cap crept back onto the stage"


def test_the_plate_governs_the_world():
    """Julian, 2026-07-27: "it has to be the scene plate reference" — after four keyframes
    came back as a dark enclosed rainforest while the real plate is an open sunlit field.

    Cause: the plate was scoped to PALETTE ONLY, so the picture defining the world got a vote
    on tint while invented prose ("corridor" — 0 uses in the script, 48 in the storyboard) got
    the vote on architecture. Architecture won every time."""
    import inspect, cb_departments as D
    s = inspect.getsource(D.prepare_cinematography)
    assert "THE PLATE IS THE WORLD" in s, (
        "the plate is a colour swatch again — words will rebuild the wrong place")
    assert "THE PLATE WINS" in s, (
        "nothing resolves plate-versus-paperwork, and the paperwork still says rainforest")


def test_the_directors_view_leads_and_the_shot_stays_flexible():
    """His words: "taking the director's view, looking at the context of the scene plate and
    the flexibility of the shot." Lens chosen to serve the feeling, never chosen first; and
    the frame must survive the first second of motion."""
    import inspect, cb_departments as D
    s = inspect.getsource(D.prepare_cinematography)
    assert "COMES FIRST" in s and "justify" in s, "the lens may be chosen before the intent again"
    assert "LEAVE THE SHOT FLEXIBLE" in s, "the frame may be pinned into a sculpture again"
    assert "which of them is bigger" in s, (
        "nothing tells the DP that two characters at wildly different depths cannot show a "
        "size relationship — the staging fault behind every failed frame today")
