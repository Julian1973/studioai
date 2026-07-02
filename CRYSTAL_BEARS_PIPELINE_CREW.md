# The Crystal Bears Pipeline — The Crew

**The frame (say this to anyone):** *It's an animation studio. Every stage of the pipeline is a department head doing their real-world job — we've just got an AI playing each one. The Show Bible is the script everyone works from; the work passes down the line department to department, exactly like a real production, and a human signs off at each gate.*

Each role below = **one skill**, with a clean input → output so they chain. The thing that flows between them is the **shot package** (the structured shot list the Director produces).

---

## The crew, in pipeline order

### 0. The Showrunner — *keeper of the bible*
- **Real job:** holds the canon — characters, world, tone, rules. Everyone defers to it.
- **Does:** supplies the locked canon (the 7 bears, crystals, feelings, Five Pillars, voice IDs, locations) to every other department; settles any "is this on-brand?" question.
- **In → Out:** the IP → `CRYSTAL_BEARS_LOCKED_CANON.md` (the single source of truth).
- **Skill:** ✅ the locked canon + `crystal-bears-master`.

### 1. The Screenwriter — *writes the story*
- **Real job:** turns an idea into a script in the show's voice.
- **Does:** writes (or ingests) the episode, bible-locked, on the Five Pillars structure; emotion is the mechanic, never a lecture.
- **In → Out:** a seed (bear + feeling + situation) → **the script**.
- **Skill:** ✅ `crystal-bears-writer-v2` / `writer` / `stack`.

### 2. The Director — *decides how it's shot* ← the creative heart
- **Real job:** breaks the script into scenes and shots; decides coverage, shot sizes, angles, camera moves, pacing, where to cut, what the camera does on each emotional beat.
- **Does:** produces the **shot list** — and tags every shot with its *intent* (the emotion/beat/intensity) so the look, the motion, the music, and the sound all stay true to the feeling.
- **In → Out:** the script → **the shot package** (the structured object every later department reads).
- **Skill:** ⚙️ **to build** — the keystone Director skill (logic currently scattered across `pipeline`/`stack`).

### 3. The Cinematographer + Production Designer — *decides how it looks*
- **Real job:** the DP owns framing, lens, lighting; the Production Designer owns the world and sets; the storyboard artist draws the key frame.
- **Does:** writes the **keyframe prompt** — composes the locked style + the locked character reference + the scene + framing + lens + lighting into one still. Bears are *referenced, never described.*
- **In → Out:** a shot → **the keyframe prompt** → the key image (nano-banana / gpt-image-1).
- **Skill:** ⚙️ **to build/consolidate** — the NB2 keyframe logic exists inside `pipeline`/`stack`.

### 4. The Camera Operator — *makes it move*
- **Real job:** operates the camera once the frame is set.
- **Does:** writes the **i2v prompt** — the keyframe is frame one, so this describes *only the change over time*: subject action, then camera move, then lens feel (+ an audio line for Veo). Tight beats verbose — this is what kills drift.
- **In → Out:** the key image → **the i2v prompt** → the clip (Seedance / Veo / Kling).
- **Skill:** ⚙️ **to build/consolidate** — Seedance/Veo logic exists inside `pipeline`/`stack`.

### 5. The Voice Director + Cast — *gives them their voices*
- **Real job:** directs the actors' performances — emotion, cadence, breath, timing.
- **Does:** turns each line into an **ElevenLabs V3 script** with the bracketed acting tags (`[whispers]`, `[cries]`, `[nervous]`), per-character settings, and the locked voice IDs. The brackets *are* the performance — plain text loses the character.
- **In → Out:** the script's dialogue → **the V3 voice script** → the dialogue audio.
- **Skill:** ✅ `crystal-bears-voice` (already world-class).

### 6. The Composer + Music Supervisor — *scores it*
- **Real job:** decides where music comes in and out, and writes/commissions it to the emotional arc.
- **Does:** writes the **Suno brief** — genre, tempo, key, instrumentation, lyrics — tied to the Five Pillars arc and each bear's musical note (the canon already gives every bear a note).
- **In → Out:** the shot package's emotional arc → **the Suno brief** → the track.
- **Skill:** ✅ logic in `pipeline`/`stack` (consolidate into its own skill).

### 7. Post — *puts it all together* (three roles)
- **The Sound Designer / Foley** — ambience beds + SFX, placed from the shot package's action/sound tags.
- **The Picture Editor** — assembles the clips into the cut; timing and pacing.
- **The Re-recording Mixer** — the mix: dialogue forward, music/ambience ducked under it, broadcast loudness (−23 LUFS), final stitch and export.
- **In → Out:** clips + voice + music + SFX → **the finished film** (ffmpeg).
- **Skill:** ⚙️ **to build** — this is the biggest gap *and* the biggest differentiator (the "AI slop → broadcast" step).

---

## Two roles that run across the whole line

### The Continuity Supervisor (Script Supervisor) — *the consistency cop*
- **Real job:** makes sure shot 47 matches shot 2 — same character, same world, screen direction, eyelines.
- **Does:** checks every shot against the locked canon and the reference images *before* anything is generated — catches drift before you spend on it.
- **Skill:** ⚙️ **to build** (new — does not exist yet; high value).

### The Producer / 1st AD — *runs the floor*
- **Real job:** keeps the production moving, schedules the work, runs the sign-off gates.
- **Does:** orchestrates the chain, holds the per-shot approve/lock gates (nothing renders to video before the key frame is approved), manages the render queue.
- **Skill:** ✅ `crystal-bears-master` (the orchestrator) → becomes the app's pipeline controller.

---

## The hand-off: the shot package

The Director produces it; every later department reads it. One shot carries:
`scene · characters (→ locked refs) · speaker (→ voice id) · shotSize · angle · movement · lens · lighting · action · dialogue · keyframePrompt · i2vPrompt · directorial intent {beat, intensity, emotion, musicMood, sfx}`

The **directorial-intent block** is what keeps the *feel* consistent — the same `intensity` that drives the close-up push-in drives the music swell and the mix energy.

---

## Build order (each role = one skill)

| Role | Skill | Status |
|------|-------|--------|
| Showrunner | locked canon + master | ✅ have |
| Screenwriter | crystal-bears-writer-v2 | ✅ have |
| Voice Director | crystal-bears-voice | ✅ have |
| Composer | (in pipeline/stack) | ✅ consolidate |
| Producer/1st AD | crystal-bears-master | ✅ have |
| **Director** | shot-breakdown skill | ⚙️ **build first (keystone)** |
| **DP / Production Designer** | keyframe-prompt skill | ⚙️ build |
| **Camera Operator** | i2v-prompt skill | ⚙️ build |
| **Continuity Supervisor** | consistency-cop skill | ⚙️ build (new) |
| **Post crew** | sound + edit + mix skill | ⚙️ build (biggest differentiator) |

Start with the **Director** (it produces the shot package everything else consumes), then DP → Camera, then Continuity, then Post.
