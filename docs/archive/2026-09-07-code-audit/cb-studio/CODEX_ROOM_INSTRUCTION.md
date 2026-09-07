# Codex Room Instruction

This file is the local contract for `/cb-studio/room.html`.

## Server Wiring

1. Add `/cb-studio/room.html` to `_APPROVED_FILES` in `cb-studio/serve.py`.
2. Add `POST /api/room-chat`.
3. The proxy forwards the `system` string untouched. system untouched means: do not trim, rewrite, prefix, summarize, or merge it; it carries cache breakpoints.
4. The proxy uses model `claude-opus-5`.
5. The proxy response shape is exactly:

```json
{"text": "..."}
```

## Verdict To Action Mapping

The room never invents production actions. It reads the live Director session and can only offer actions whose IDs are present in the current session action set.

| Room verdict | Director action id |
| --- | --- |
| Approve SEE | `accept-keyframe` |
| Reject SEE | `iterate-keyframe` |
| Approve HEAR | `accept-voice` |
| Reject HEAR | `iterate-voice` |
| Approve WATCH | `accept-animation` |
| Reject WATCH | `iterate-animation` |
| Reopen approved shot | `reopen-shot` |
| Approve master | `accept-master` |
| Reject master | `iterate-master` |

Reject-family actions require a plain-English note and must send that note to `/api/director-action`.

Confirmed reject-family action IDs that accept `note` in the current server:

- `iterate-keyframe`
- `iterate-voice`
- `iterate-animation`
- `iterate-master`
- `reopen-shot`

## Acceptance List

- `/cb-studio/room.html` is served by the local Studio allowlist.
- `POST /api/room-chat` exists.
- `/api/room-chat` forwards `system` untouched.
- `/api/room-chat` uses model `claude-opus-5`.
- `/api/room-chat` returns `{"text": ...}`.
- The room maps verdicts only to live Director action IDs.
- Reject-family actions require and forward `note`.
