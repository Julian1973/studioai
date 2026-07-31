# Legal / Licensing Checklist

Tracking artifact only. Nothing on this page has been resolved, negotiated, or actioned by
software — it exists so the items the Legal/Business Affairs review named as required before any
broadcaster conversation proceeds are visible and not lost, not so they can be checked off by a
tool. Every item is Julian's own call, several requiring a lawyer, none of them mine to execute.

Source: the five-department Pixar-panel review (2026-07-08), Legal/Business Affairs lens, in
response to Julian's question "if you are a Pixar studio right now... what would they change?" —
see CLAUDE.md rule 57 for the full context and what was built from the same review.

---

## 1. Voice chain-of-title — per character

**Status: NOT YET RESOLVED**

Every principal and recurring character speaks through an ElevenLabs voice
(`characters.json`'s `voiceId` field, 11 characters currently mapped). Before any broadcast or
syndication conversation, each of those 11 voices needs a written record of:

- Whether the voice is a licensed ElevenLabs stock voice, a cloned voice (from what source
  recording, whose voice, under what consent), or fully synthetic.
- If cloned: documented consent from the person whose voice was cloned, covering the specific
  uses this show intends (broadcast, streaming, merchandising, territorial distribution).
- Whether that consent — if it exists at all today — was ever scoped to "an animated children's
  show," or to something narrower.

**Why this matters:** a broadcaster or distributor's own legal team will ask this question before
signing anything, and "we don't have that documented" stops the conversation cold at a much worse
moment than now.

**Action needed (Julian, likely with counsel):** produce or commission that written record for
each of the 11 voices, character by character.

---

## 2. ElevenLabs terms — confirm the ENTERPRISE tier, not the default ToS

**Status: NOT YET RESOLVED**

The panel's finding: ElevenLabs' default consumer/API terms of service are very unlikely to grant
the rights a broadcast/syndication/territorial/merchandising deal actually requires. Enterprise
voice-AI agreements typically carve out broadcast rights, geographic scope, and downstream
merchandising separately, and often require a distinct signed agreement — not just a higher
pricing tier.

**Why this matters:** if the show's audio was produced entirely under a default consumer ToS, the
studio may not actually hold the rights it would need to license the finished episodes to a
broadcaster, regardless of how good the episodes are.

**Action needed (Julian):** contact ElevenLabs directly, ask specifically about enterprise terms
for broadcast/syndication/territorial/merchandising rights (not the default plan), and get that
confirmation in writing before relying on it in any broadcaster conversation.

---

## 3. AI-generated music — copyrightability

**Status: NOT YET RESOLVED**

Scene music/score is currently produced by Seedance's own native generation (timed to the
picture) with an ElevenLabs Music bed as a fallback (`cb_post.py`'s `AUTO_MUSIC_BED`). The
copyright status of AI-generated music — whether it can be copyrighted at all, who would hold
that copyright if so, and whether a broadcaster would accept AI-generated score in a delivered
master without a human-composition credit — is an unsettled legal question, not a software one.

**Why this matters:** a broadcaster's standards-and-practices or legal team may require either a
clear copyright chain for the score or a human composer credit; either could affect delivery
requirements or the deal itself.

**Action needed (Julian, likely with counsel):** get a legal opinion on the current copyright
status of the show's AI-generated music before it becomes a delivery blocker.

---

## 4. Guild / union exposure memo

**Status: NOT YET RESOLVED**

AI-voiced, AI-animated production of a children's show touches territory (voice performance,
animation labor) that human-performer and animator guilds (e.g. SAG-AFTRA) have active positions
on. The panel's finding is that this exposure has not been assessed at all — not that it is
necessarily a problem, only that nobody has checked.

**Why this matters:** guild exposure can affect distribution options, casting/credit
requirements, or invite disputes that are far cheaper to understand in advance than to discover
mid-negotiation.

**Action needed (Julian, likely with counsel):** commission a short memo assessing what guild
exposure, if any, this production model creates, before entering any distribution or
broadcaster conversation.

---

## What this document is not

It is not legal advice, does not represent that any of the above has been checked or is fine, and
takes no action on any item — no outreach, no signature, no filing. It is a checklist so these
four items are visible together in one place. Update the status line directly when Julian
resolves each one; do not mark anything resolved based on inference or absence of a problem found
elsewhere.
