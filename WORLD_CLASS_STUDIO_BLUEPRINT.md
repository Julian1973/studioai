# World-Class Studio Blueprint

Version: 1.0, 1 August 2026

## The promise

Crystal Bears Studio exists to turn an approved script into a finished animated master
without losing the authored joke, the emotional truth, the character, the image or the
evidence that makes the result trustworthy.

The software can make the first production pass dramatically faster. It cannot guarantee
an award, replace taste or manufacture a Pixar finish by adding "cinematic" to a prompt.
Its job is to make excellent choices explicit early, preserve them through every handoff,
show the director the result in context and make the cheapest useful correction obvious.

## What the best work teaches us

This blueprint uses first-party and institutional material rather than studio mythology.

### Authored truth before scale

- Ludo describes itself as taking original stories from script to screen under one roof.
  ABC's account of the Bluey process shows the practical shape: authored scripts,
  storyboards, a dialogue-timed animatic used as the production recipe, episode-specific
  art direction, bespoke score, Foley, final mix and screenings where the team watches
  children for the laugh. The transferable lesson is not Bluey's drawing style. It is the
  short feedback distance between story, performance, editorial and the audience.
- Pixar's official learning material starts with character want versus need, obstacles,
  stakes, beats, theme and storyreels. Film grammar then distinguishes major and minor
  beats, shot scale, camera dynamics and storyboarding. Lighting is taught as a story and
  emotion system through color scripts, master lighting and shot lighting.
- Pixar's own statement of values says emotional universality begins in specific,
  personally truthful material. The pipeline must therefore preserve a point of view,
  not average it into generic family entertainment.

### A full pipeline, not one clever model

- ICON's published full-service pipeline names design, storyboarding, editing, modeling,
  rigging, grooming, animation, character effects, lighting, VFX, compositing, post and
  sound. Rainbow CGI similarly couples technical research with serial and feature
  production. Their lesson is departmental ownership and a complete finish path.
- OpenUSD exists because modeling, shading, animation, lighting, effects and rendering
  need a robust shared scene description. OpenTimelineIO keeps editorial order and cut
  duration separate from media. ACES and its metadata preserve the intended view of an
  image through VFX, finishing and archival. Crystal Bears does not need to imitate a
  feature studio's infrastructure today, but its contracts must keep those boundaries.
- Autodesk Flow Production Tracking ties shots to department tasks and review versions.
  Its review guidance keeps the right version, notes and outcome together. Adobe
  Productions similarly uses references instead of duplicate assets and locking instead
  of optimistic overwrites.

### Context helps, but context is not authority

InVideo's current Agent One Context product is useful interaction research: project
purpose, standing rules, world building, inspiration, visual language, knowledge and
review agents live beside the work so creators do not repeat themselves. Crystal Bears
adopts the calm, selection-aware briefing experience, but with a stronger boundary:

- signed canon and immutable script versions are facts;
- episode, scene and shot briefs are derived proposals;
- no agent silently promotes a proposal into canon;
- no chat turn becomes production approval;
- no provider, retry or spend decision is inferred from conversational enthusiasm.

### Provider reality

As of 1 August 2026, the current public BytePlus and ByteDance documentation names
Dreamina Seedance **2.0**, not 2.5. It supports text, image, video and audio references,
up to nine images, three videos and three audio assets, and up to 15-second generated
audio-video output. First-frame, first-and-last-frame and multimodal-reference workflows
are distinct API scenarios. The Studio must keep 2.0 as the only live named route until a
2.5 model ID, account entitlement and one non-production conformance test are verified.

## The production model

```mermaid
flowchart LR
    A["Signed show context"] --> B["Immutable script"]
    B --> C["Episode vision"]
    C --> D["Scene treatments"]
    D --> E["Beat emotion, comedy and power contracts"]
    E --> F["Shot conference and cinematography"]
    F --> G["Voice and timed storyreel"]
    G --> H["Look, layout and opening frames"]
    H --> I["Controlled generation units"]
    I --> J["Dailies on actual media"]
    J --> K["Editorial, sound, color and QC"]
    K --> L["Approved master and evidence pack"]
```

## The creative contracts

Every scene must answer these before media spend:

1. **Audience**: what does the child feel now, what does the adult recognise and what is
   the one final feeling?
2. **Story**: whose scene is it, what changes, what choice causes the change and what is
   carried forward?
3. **Character**: what does each performer want from the other character, which locked
   trait is under pressure and what observable behaviour makes substitution impossible?
4. **Emotion**: entry state, pressure, turn, exit state, visible evidence and whether the
   audience is ahead of, with or behind the character.
5. **Comedy**: setup, expectation, disruption, reaction, button and hold. BIG physical
   comedy also owns contact, weight, readable silhouette and payoff shape.
6. **Power**: canonical bearer, trigger, exact call occurrence when spoken, manifestation,
   emotional meaning, cost or consequence, continuity result and prohibited inventions.
7. **Cinematography**: story point of view, scale, lens intent, height, composition, depth,
   camera behaviour, focus, lighting function, palette movement and motivated cut.
8. **Sound**: exact dialogue occurrence, performance intention, breath and pause, room
   perspective, signature effects, score function and the moments where music gets out of
   the way.

These are authored intentions, not score-padding fields. A field that does not change the
work should not exist. The provider receives only concise, observable instructions distilled
from them; it never receives internal psychology, review argument or walls of safeguards.

## The quality compass

The creative workspace reports five calm dimensions. A dimension may be `clear`, `needs
attention`, `waiting` or `unassessed`; it is never declared good merely because a file exists.

| Dimension | Clear only when |
|---|---|
| Story | script, canon, dialogue occurrences, treatment and beat order are current |
| Performance | character-specific acting and voice intentions are approved and visible |
| Picture | look, camera, frame, continuity and actual rendered media support the story |
| Sound | dialogue, performance, timing, ambience, score, effects and mix are current |
| Finish | conform, captions, stems, color, loudness, PSE/QC and master review are proven |

Automated checks protect identity, lineage, timing, media integrity and delivery. They do
not decide whether Zenny's deadpan hold is funny or whether Fuzzby's chaos has heart. Those
remain director decisions made while watching the cut.

## The creative interface

The default scene workspace is **Now / Story / Canvas / Notes**:

- **Now** gives one context-aware next action and any human decision that truly blocks it.
- **Story** keeps beats and shots in script order and preserves selection across views.
- **Canvas** shows the current treatment, frame, performance, clip or assembled sequence.
- **Notes** holds the editable direction, candidate comparison and decision in context.
- **Evidence** is collapsed by default and contains hashes, policy, provider payload, cost,
  technical blockers and history.

Safety remains fail closed in the engine. The interface does not make safety feel like a
maze: completed phases stay quiet, future phases read as waiting, and only the current
creative decision receives emphasis. Conversation is a control surface, never the source
of truth and never a substitute for direct media inspection.

## Multi-IP architecture

The reusable studio has four layers:

1. **Studio kernel**: immutable versions, approvals, leases, spend tokens, provider ports,
   review, post, delivery and evidence.
2. **Show profile**: format, audience, aspect ratio, canon paths, laws, quality profile,
   department skills and provider policy.
3. **Signed show context**: bible, characters, relationships, locations, props, powers,
   voices, visual language, sonic language and rights provenance.
4. **Production briefs**: episode, scene, shot and delivery-specific derived contracts.

No new IP should require editing the kernel. It should start by supplying a valid profile
and content bundle, then fail with named missing content rather than fall through to Crystal
Bears vocabulary.

## Delivery baseline

### Implemented and proven

The current scene-post path creates transactional 16:9 and 9:16 H.264 masters, exact-dialogue
SRT and VTT captions, and a 24-bit programme-mix WAV. It probes the finished artifacts for
24 fps, YUV420p, Rec.709 metadata, AAC, 48 kHz stereo, dimensions and duration, then measures
integrated loudness and true peak against the chosen destination profile. Hashes, source
order, conform decisions and technical results travel in the immutable post manifest. These
checks never substitute for the human final-picture, performance and sound review.

### Delivery expansion

True dialogue, music and effects stems require upstream generators or a sound edit that
actually keeps those sources separate; a combined programme track is never mislabeled as
stems. Episode-level mezzanine assembly, poster frames, rights manifests, destination-specific
caption validation and a validated photosensitivity test remain explicit delivery work, not
capabilities inferred from scene-master creation. EBU R 128 currently defines -23 LUFS for
European broadcast; every distributor profile still requires a current specification check.

## Sources

- Pixar, [Pixar in a Box](https://www.pixar.com/pixar-in-a-box)
- Pixar and Khan Academy, [The art of storytelling and production lessons](https://www.khanacademy.org/computing/pixar)
- Pixar, [Life at Pixar](https://www.pixar.com/life-at-pixar/)
- ABC, [How Bluey is made at Ludo Studio](https://www.abc.net.au/news/2019-12-02/i-took-my-toddler-to-see-where-bluey-is-made-ludo-studio/11742386)
- Ludo Studio, [About](https://ludostudio.com.au/about)
- ICON Creative Studio, [Full-service CG pipeline](https://www.iconcreativestudio.com/studio)
- Rainbow, [Rainbow CGI](https://www.rbw.it/en/about/the-group/rainbow-cgi/)
- Pixar, [Technology libraries](https://www.pixar.com/technology-libraries)
- OpenUSD, [Introduction](https://openusd.org/release/intro.html)
- Autodesk, [Flow Production Tracking schema](https://help.autodesk.com/cloudhelp/ENU/SG-Administrator/files/ar-get-started/SG_Administrator_ar_get_started_ar_schema_html.html)
- Autodesk, [Reviewing work](https://help.autodesk.com/cloudhelp/ENU/SG-Automotive/files/am-getting-started/SG_Automotive_am_get_started_am_reviewing_html.html)
- Adobe, [Productions in Premiere](https://helpx.adobe.com/au/premiere/desktop/collaborate-with-others/collaborate-using-productions/about-productions.html)
- InVideo, [Using Context to guide Agent One](https://help.invideo.io/en/articles/14718442-using-context-to-guide-your-agent)
- ByteDance Seed, [Seedance 2.0 official launch](https://seed.bytedance.com/blog/seedance-2-0-official-launch)
- BytePlus, [Seedance video generation API](https://docs.byteplus.com/en/docs/modelark/1520757)
- ACES, [System overview](https://draftdocs.acescentral.com/background/overview/)
- EBU, [R 128 loudness](https://tech.ebu.ch/loudness/)
