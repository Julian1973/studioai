# Crystal Bears — signature SFX one-shots

This directory holds the show's own small library of signature comedy sound effects, referenced
by `shows/crystal-bears/canon/sfx_library.json` (read via `engine/config/sfx_library.json`, the
usual `engine/config` -> `shows/crystal-bears/canon` symlink).

**Nothing is here yet.** Four files are expected, matching the manifest:

- `fwip.mp3` — the leaf-impact snap-and-bounce (FWIP)
- `thup.mp3` — the soft rubbery tumble/bounce impact (THUP)
- `pollen_puff.mp3` — the flower-whoomp-plus-pollen-release (POLLEN_PUFF)
- `pop.mp3` — the triumphant pop-up finisher (POP)

`engine/cb_post.py`'s SFX-sweetening step (`sweeten_cues_for_scene`/`mix(..., sfx_layers=...)`)
checks each of these paths at render time and silently skips any cue whose file isn't present —
Gate 5 never blocks or fails because a sound is missing here. Drop a real recorded or licensed
`.mp3` at the named path to activate that cue; no code change is needed.
