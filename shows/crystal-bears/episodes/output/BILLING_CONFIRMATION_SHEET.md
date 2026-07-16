# BILLING CONFIRMATION SHEET — zero-spend, for Julian's informed approval
_2026-07-16 · nothing generated · **FAL: CONFIRMED per model by Julian (2026-07-16)** — keyframe at conservative max $0.144 ex tax; video at $0.3034/sec ex tax (the higher of fal's two printed figures, ruled alternative expressions of one billing basis, not cumulative). Billing profile v2026-07-16.2 records both. **ELEVENLABS: remains UNCONFIRMED** pending Julian's actual plan and cadence._

## Entry 1 — Voice
| Field | Value |
|---|---|
| Provider | ElevenLabs |
| Exact API model & endpoint | `eleven_v3` via `POST /v1/text-to-dialogue` (api.elevenlabs.io) |
| Operation | Voice (per-shot dialogue track) |
| Account plan | **Pro (ASSUMED — unverifiable: API key is generation-scoped, 401 on subscription read)** |
| Billing cadence | **Monthly (ASSUMED)** |
| Charging unit | Credit = 1 character of input text (v3 meter) |
| Published unit price | $99.00 / 600,000 credits → **$0.000165/char ($0.165 per 1,000 chars)** |
| Resolution/duration assumptions | n/a (character-metered, duration-independent) |
| Official source URL | https://elevenlabs.io/pricing |
| Effective date | 2026-07-16 |
| Tax treatment | Published price excludes tax; VAT applied at invoice per account country |
| Rate basis | **Publicly derived** from the published Pro plan — NOT account-specific until plan+cadence confirmed |

## Entry 2 — Keyframe (image)
| Field | Value |
|---|---|
| Provider | fal.ai |
| Exact API model & endpoint | `bytedance/seedream/v5/pro/edit` (Seedream 5.0 Pro, edit/reference mode) |
| Operation | Keyframe (opener opening-frame image) |
| Account plan | n/a — usage-metered, no plan tier |
| Billing cadence | Pay-as-you-go, per generation |
| Charging unit | Per output image + per additional input image |
| Published unit price | ≤1536×1536: $0.0675/image · 1536²–2048² (2K): **$0.135/image** · +$0.0045 per input image after the first (first input free) |
| Resolution/duration assumptions | Our keyframes generate at 2K → $0.135 base; 1.B1.S1 uses **3 input references** (Zenny, Fuzzby, plate) → 2 chargeable extras = +$0.009 |
| Official source URL | https://fal.ai/models/bytedance/seedream/v5/pro/edit |
| Effective date | 2026-07-16 (page marks pricing "tentative") |
| Tax treatment | Published price excludes tax; tax per fal invoice jurisdiction |
| Rate basis | **Publicly derived** (per-model metered rate, account-neutral) — matches the code's $0.144/keyframe estimate exactly |

## Entry 3 — Video candidate
| Field | Value |
|---|---|
| Provider | fal.ai |
| Exact API model & endpoint | `bytedance/seedance-2.0/reference-to-video` (standard tier; the fast tier `…/fast/reference-to-video` is NOT used for production) |
| Operation | Video candidate (one per candidate in a batch) |
| Account plan | n/a — usage-metered |
| Billing cadence | Pay-as-you-go, per second generated |
| Charging unit | Per second of output video |
| Published unit price | 720p standard, no video input: page tier table **$0.3024/sec**; page prose states **$0.3034/sec** (an internal discrepancy on fal's own page — the HIGHER figure is used for the maximum below) · 1080p: $0.682/sec (not used) · audio generation included at no extra cost |
| Resolution/duration assumptions | **720p** (our default), duration = the shot's exact designed seconds (1.B1.S1 = 6s), audio-driven lip-sync included free |
| Official source URL | https://fal.ai/models/bytedance/seedance-2.0/reference-to-video |
| Effective date | 2026-07-16 |
| Tax treatment | Published price excludes tax; tax per fal invoice jurisdiction |
| Rate basis | **Publicly derived** — NOTE: the code's current estimate rate is $0.30/sec, ~1% BELOW the official $0.3024–0.3034; alignment to the confirmed figure happens at your confirmation (a billing-profile edit, no code change) |

## Maximum estimated cost — the first experiment (ex tax)
| Item | Basis | Max cost |
|---|---|---|
| 1 × 1.B1.S1 keyframe | 2K ($0.135) + 2 extra input refs ($0.009) | **$0.144** |
| 3 × Seedance candidates | 3 × 6s × $0.3034 (higher of fal's two printed 720p figures) | **$5.4612** |
| Additional provider charges | fal file uploads/hosting: not billed per fal docs · Seedance audio: included free · ElevenLabs: $0 (voice already generated; no new voice in this experiment) | **$0.00 identified** |
| **MAXIMUM TOTAL** | | **$5.61 ex tax** (code's disclosure will show $5.40 until the rate is aligned on your confirmation) |

Nothing fires until: (1) you confirm each entry above (or correct it), (2) your timing-slate
verdict, (3) your separate keyframe approval, (4) the batch's own spend disclosure + token.
