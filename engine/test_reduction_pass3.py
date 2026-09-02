"""Regression proofs for the Pass 3 runtime boundary."""
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = (ROOT / "cb-studio/serve.py").read_text(encoding="utf-8")


def test_removed_restart_route_is_not_reachable_from_server_or_current_ui():
    ui = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "cb-studio").glob("*.js"))
    assert 'self.path == "/api/restart"' not in SERVER
    assert "/api/restart" not in ui


def test_legacy_server_wrappers_have_no_runtime_definitions():
    for name in ("fire_gate", "approve_gate", "unapprove_gate", "set_master_studio",
                 "clear_master_studio", "_gate_ready", "regen_shot", "gen_audio_beat",
                 "gen_keyframe_beat", "render_beat_clip", "approve_beat",
                 "rebuild_keyframes"):
        assert f"def {name}(" not in SERVER


def test_four_phase_entry_points_remain_present():
    for route in ("/api/story-intake-decide", "/api/episode-production-start",
                  "/api/shot-run", "/api/director-action", "/api/stop"):
        assert route in SERVER
