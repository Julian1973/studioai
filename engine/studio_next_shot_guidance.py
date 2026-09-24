"""Give the producer a text-only, source-locked next-shot recommendation."""
from contextlib import nullcontext
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["hard-cut", "exact-frame-relay"]
    why: str = Field(min_length=1, max_length=220)


SYSTEM = """You are Luna, helping a producer move between approved animation shots.
The approved Director Card fixes the transition. Do not change it, invent a new
camera choice, or claim to have seen images. Return the supplied transition mode
unchanged and one plain, specific reason grounded only in the approved fields.
Keep the reason under 35 words. For a hard cut, say the previous final frame is
continuity context and the next shot uses its own approved opening. For an exact
frame relay, say the previous approved final frame carries into the next opening."""


def _text(value, limit=500):
    return " ".join(str(value or "").split())[:limit]


def _result(*, mode, current_id, next_id, reason, source, ready=True):
    labels = {
        "hard-cut": "Hard cut · new directed opening",
        "exact-frame-relay": "Carry the exact approved final frame",
        "review-see": "Review the next opening in SEE",
    }
    return {
        "ready": ready,
        "mode": mode,
        "label": labels[mode],
        "currentShotId": current_id,
        "nextShotId": next_id,
        "reason": reason,
        "source": source,
        "textOnly": True,
    }


def recommend(server, scope):
    """Read approved records; Luna may explain, never select or alter transition."""
    from studio_journey import scope_key
    from studio_journey_native import read

    scope_key(scope)
    if scope.get("projectId") != "crystal-bears":
        raise ValueError("Next-shot guidance is only available for Crystal Bears.")
    package, _board, current, ledger = read(server.ROOT, scope)
    shots = package.get("shots") or []
    current_id = str(scope.get("unit") or "")
    index = next((i for i, shot in enumerate(shots)
                  if shot.get("shotId") == current_id), -1)
    if index < 0 or index + 1 >= len(shots):
        raise ValueError("There is no next shot in the current scene package.")
    next_shot = shots[index + 1]
    next_id = str(next_shot.get("shotId") or "")
    approval = ledger.get("approval") or {}
    current_accepted = (
        ledger.get("status") == "approved"
        and bool(ledger.get("approvedTake"))
        and bool(ledger.get("harvestFrame"))
        and approval.get("packageRevision") == package.get("revision")
    )
    if not current_accepted:
        return _result(
            mode="review-see", current_id=current_id, next_id=next_id,
            reason=f"Review {current_id} before continuing. Its current approved final frame is not confirmed.",
            source="Studio approval check", ready=False)

    transition = next_shot.get("shotTransition") or {}
    source_id = (transition.get("stateSourceShotId")
                 or next_shot.get("stateSourceShotId")
                 or next_shot.get("sourceShotId"))
    transition_type = transition.get("type")
    if source_id != current_id:
        mode = "review-see"
        reason = (f"The approved handoff does not name {current_id} as its source. "
                  "Open SEE to review the next opening direction.")
        return _result(mode=mode, current_id=current_id, next_id=next_id,
                       reason=reason, source="Approved Director Card", ready=True)
    if transition_type == "cut":
        mode = "hard-cut"
        fallback = (f"Hard cut from {current_id}. Its final frame informs continuity only; "
                    f"{next_id} starts from its own approved opening direction.")
    elif (transition_type == "continuation"
          and next_shot.get("sourceType") == "relay"
          and next_shot.get("sourceShotId") == current_id):
        mode = "exact-frame-relay"
        fallback = (f"Carry {current_id}'s exact approved final frame into {next_id}'s opening. "
                    "Keep the approved next-shot action and direction.")
    else:
        return _result(
            mode="review-see", current_id=current_id, next_id=next_id,
            reason=f"Open SEE to inspect {next_id}'s approved opening; the handoff does not specify a cut or exact-frame carry.",
            source="Approved Director Card", ready=True)

    reason, source = fallback, "Approved Director Card"
    try:
        from cb_director_chat import CHAT_MODEL
        import cb_episode_budget
        import cb_llm

        context = {
            "mode": mode,
            "previous": {
                "shotId": current_id,
                "approvedPurpose": _text(current.get("purpose")),
                "approvedEnding": _text(current.get("visualPayoff")),
                "continuityOut": _text(current.get("continuityOut")),
            },
            "next": {
                "shotId": next_id,
                "approvedPurpose": _text(next_shot.get("purpose")),
                "approvedTransitionReason": _text(transition.get("reason")),
                "approvedOpening": _text(transition.get("openingImage") or next_shot.get("openingPose")),
                "approvedCamera": _text(transition.get("camera") or next_shot.get("camera")),
            },
        }
        episode = str(scope.get("episode") or "")
        budget = cb_episode_budget.quote(episode, None, "text:producer-next-shot-guidance")
        with (budget if episode else nullcontext()):
            answer = cb_llm.structured(
                SYSTEM, json.dumps(context, ensure_ascii=False), Recommendation,
                model=CHAT_MODEL, tier="standard", label="producer-next-shot-guidance",
                max_output_tokens=120, reasoning_effort="low", reuse=True)
        if answer.mode == mode:
            reason, source = _text(answer.why, 220), "Luna · approved direction"
    except (Exception, SystemExit):
        pass
    return _result(mode=mode, current_id=current_id, next_id=next_id,
                   reason=reason, source=source, ready=True)
