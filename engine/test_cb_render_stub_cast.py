"""A scripted stub role costs its own wearable-state lock, never the whole text brief.

CLAUDE.md rule 87: a stub never blocks a text-only pass; the strict rule belongs on the paid
stages that put a character on screen or give it a voice. _shot_context reads a provider identity
record only to derive a "approved wearable state" note for the brief, and that read used to raise
— so one stub in the frame refused SEE, HEAR and WATCH direction outright, all three zero-spend,
for a reference none of them would have used (2026-09-02, Teacher in The Box Monsters' S1.SH01).
"""
import cb_render


def _context(monkeypatch, records):
    shot = {"shotId": "S1.SH01", "charactersInFrame": list(records)}
    monkeypatch.setattr(cb_render, "_shot_creative_contract_view",
                        lambda pkg, s, scene, episode: dict(shot))
    monkeypatch.setattr(cb_render, "_with_effective_dialogue_timing", lambda view, led: view)
    monkeypatch.setattr(cb_render, "_characters_cfg", dict)
    monkeypatch.setattr(cb_render, "_scene_continuity_locks", lambda pkg, scene: {})

    def identity(name, characters_cfg, usage="keyframe", **_kwargs):
        record = records[name]
        if record is None:
            raise cb_render.Refused(
                f"REFUSED — {name} has no locked single-subject provider identity pack; "
                "add and canon-lock one before generation. No provider was contacted")
        return record

    monkeypatch.setattr(cb_render, "_provider_identity_record", identity)
    return cb_render._shot_context({}, shot, {}, "1", "Ep1")


def test_a_stub_in_frame_does_not_refuse_the_text_brief(monkeypatch, capsys):
    context = _context(monkeypatch, {
        "Patch": {"character": "Patch", "characterState": "default",
                  "distinguishingFeatures": ["wears a red collar"]},
        "Teacher": None,
    })

    locks = context["shot"]["characterStateLocks"]
    assert "Patch" in locks and "red collar" in locks["Patch"]
    assert "Teacher" not in locks
    printed = capsys.readouterr().out
    assert "CAST CANON INCOMPLETE" in printed and "Teacher" in printed


def test_every_stub_in_frame_still_builds_a_brief(monkeypatch):
    context = _context(monkeypatch, {"Teacher": None, "Classmate": None})
    # No lock survives, and no lock block is invented either — but the brief exists.
    assert "characterStateLocks" not in context["shot"]
    assert context["shot"]["shotId"] == "S1.SH01"


def test_the_paid_attachment_path_keeps_the_strict_rule():
    """Only the text read is forgiving: the stage that actually attaches an image still refuses."""
    source = cb_render._slot_path_for_role.__code__
    assert "_provider_identity_record" in cb_render.__dict__
    # _slot_path_for_role indexes the record's own path, so a Refused from a missing pack
    # propagates there exactly as before — the guard added for the brief is local to _shot_context.
    import inspect
    assert "_provider_identity_record" in inspect.getsource(cb_render._slot_path_for_role)
    assert "except Refused" not in inspect.getsource(cb_render._slot_path_for_role)
    assert source.co_argcount >= 1
