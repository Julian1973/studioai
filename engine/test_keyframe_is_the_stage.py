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


def test_both_chairs_are_bound_to_the_pictures_not_just_the_keyframe():
    """THE COIN-TOSS BUG (2026-07-27, Julian, watching the first take fired off the corrected
    keyframe: "the scene doesnt deliver").

    THE PLATE IS THE WORLD shipped that morning into prepare_cinematography — the chair that
    writes the STILL. prepare_animation — the chair that writes the FIFTEEN SECONDS — never
    got it. The take fired at 07:56 named "corridor" five times and "ceiling" twice over an
    opening frame that is an open sunlit field, and the words beat the picture: the first
    second of footage is a dirt path between walls of flowers.

    A law that governs one chair and not the other is not a law. It is a coin toss over which
    chair happens to write the sentence that survives into the render. This binds both."""
    import inspect, cb_departments as D
    still = inspect.getsource(D.prepare_cinematography)
    take = inspect.getsource(D.prepare_animation)
    for name, src, headline, wins in (
            ("keyframe", still, "THE PLATE IS THE WORLD", "THE PLATE WINS"),
            ("take", take, "THE PICTURES ARE THE WORLD", "THE PICTURES WIN")):
        assert headline in src, (
            f"the {name} chair may build a world out of vocabulary again — this is how "
            f"'corridor' (0 uses in the script, 48 in the storyboard) kept winning")
        assert wins in src, f"nothing resolves picture-versus-paperwork for the {name} chair"
    # The specific architecture the renders kept inventing, named in both charges so neither
    # can be read as a general plea for restraint.
    for name, src in (("keyframe", still), ("take", take)):
        assert "corridor" in src and "ceiling" in src, (
            f"the {name} chair no longer names the architecture it must not build")


def test_the_take_has_to_go_somewhere():
    """The same take holds one hovering centred character for its whole length — it begins and
    ends on near-identical frames. The keyframe is charged to be a FORGIVING START; nothing
    charged the take to LEAVE it."""
    import inspect, cb_departments as D
    s = inspect.getsource(D.prepare_animation)
    assert "MUST TRAVEL" in s, "a take may open and close on the same frame again"
    # Asserted on a fragment that does not span a source line break — this charge is built
    # from adjacent string literals, so a phrase split across two of them is present in the
    # VALUE and absent from the SOURCE. The first draft of this test asserted the whole
    # sentence and failed against a rule that was correctly in place.
    assert "where they live" in s, (
        "@图1 is not stated as a starting point only — it can still read as the pose to hold")
    assert "could not have shown you" in s, (
        "nothing states the test for whether the take moved — an end frame that the opening "
        "frame could have shown you means nothing happened")


def test_the_take_reads_the_approved_keyframe_before_it_writes():
    """Julian, 2026-07-27: "The direction really needs to be able to look at the keyframe to
    be able to start the direction from that moment, rather than it not doing so."

    The ORDERING was never broken — _anchor_for refuses to prepare a take without an APPROVED
    keyframe, and on the failing shot the keyframe was approved at 07:47:33 and the direction
    at 07:51:25. The writer HAD the right picture attached as @图1. It had nowhere to look at
    it: AnimationDirection went straight to providerPrompt, so the prose was written from the
    shot's paperwork (which says rainforest and corridor) and "corridor" reached the fired
    prompt five times over an open sunlit meadow.

    In a structured output FIELD ORDER IS REASONING ORDER. This binds the read above the
    prose, the same way frameLogic binds the staging decision above the keyframe's prose."""
    import cb_departments as D
    for model, first in ((D.AnimationDirection, "openingFrameRead"),
                         (D.CinematographyDirection, "frameLogic")):
        f = list(model.model_fields)
        assert first in f, f"{model.__name__} can write prose with nothing decided first"
        assert f.index(first) < f.index("providerPrompt"), (
            f"{first} sits BELOW providerPrompt — the prose would be written before the "
            f"thinking, which is the same as not having the field at all")
        assert model.model_fields[first].is_required(), f"{first} is skippable"


def test_the_read_names_the_four_things_that_failed():
    """A read that says "looks nice" is not a read. Each part maps to a specific, named
    failure from the real footage."""
    import cb_departments as D
    d = D.AnimationDirection.model_fields["openingFrameRead"].description or ""
    for fragment, failure in (
            ("WHAT KIND OF PLACE", "the corridor built out of vocabulary over a meadow"),
            ("size relative to each other", "Zenny pushed to a speck so scale cannot read"),
            ("AFFORD", "the stage has to be flexible enough for the performance"),
            ("WHERE DOES IT GO", "a take that opens and closes on the same held pose")):
        assert fragment in d, f"the read no longer covers: {failure}"
    assert "never the paperwork" in d, (
        "nothing resolves picture-versus-paperwork inside the read itself")


def test_the_handbook_is_the_writers_bible_not_a_document_i_read():
    """Julian, 2026-07-27: "I need you to use the cinematography as the prompt bible — we
    create it as a working engine that the director feeds his shot into with the opening frame
    and we build out the delivery for the seedance prompt."

    Before this it was a .docx I read and hand-applied to one shot. That is not an engine; it
    is me, and it does not survive me. It now loads VERBATIM into the Animation Director's own
    curriculum on every prepare, ahead of the two craft documents — decide the shot, then write
    it well, never the reverse."""
    import cb_departments as D
    curriculum, _ = D._craft_curriculum(None)
    assert "AI_CINEMATOGRAPHY_HANDBOOK" in curriculum, (
        "the prompt bible is not being loaded — the writer is back to guessing the shot")
    # It leads. Its own §1: "starting with camera angles encourages pretty but empty motion."
    assert curriculum.index("AI_CINEMATOGRAPHY_HANDBOOK") < curriculum.index("PROMPT_CRAFT_STANDARD"), \
        "register is being taught before the shot is decided"
    for law, why in (
            ("EYES", "the reaction ladder — the thing that keeps failing on every face"),
            ("BREATH", "the reaction ladder's second rung"),
            ("Direct the change", "the book's central doctrine"),
            ("CUT TEST", "the test that stops decorative cuts"),
            ("PRIORITY RULE", "primary explicit, secondary concise, ambient quiet")):
        assert law in curriculum, f"the bible lost: {why}"
    # The one place it disagrees with this studio's own measured corpus must stay named.
    assert "STUDIO AMENDMENT" in curriculum and "722" in curriculum, (
        "the word-count amendment is gone — a numeric cap will creep back, and one was already "
        "deleted once for making the footage worse")


def test_the_priority_rule_is_obeyed_not_merely_read():
    """The handbook states the priority rule in its own §2, and the writer read it and ignored
    it — the very next prompt came back with the wake rocking her, the lavender whipping, the
    clover nodding and the pollen turning in the flare, none of it asked for, each one a whole
    sentence eating seconds the somersaults needed. A rule the writer has READ is not yet a
    rule the writer OBEYS."""
    import inspect, cb_departments as D
    s = inspect.getsource(D.prepare_animation)
    assert "THE PRIORITY RULE" in s, "the charge no longer budgets ink by tier"
    assert "AMBIENT LIFE" in s and "QUIET" in s, "ambient life can take whole sentences again"
    assert "count what you have asked to physically HAPPEN" in s, (
        "the writer has no instruction to check its own event count against the seconds")
