# Spec: "Guide Me" — AI Reading Companion

**Date:** 2026-06-19 · **Branch:** `changev4` (feature-test line; preview only, NOT deployed to `main`/live until approved)

## Context
The "Behold My Messenger" audiobook site (`index.html` + `book-1..5.html`, static, Cloudflare
Pages) currently offers no guidance for *where to start* or *what to listen to*. The owner wants
the site to feel "intelligent": a reader describes what they're facing today, and an assistant
recommends specific chapters to listen to and builds a personalized listening plan — strictly from
the books' own teaching. This adds a small AI backend to an otherwise fully static site.

## Goals
- A reader can type a free-text problem ("I feel anxious", "I doubt God", "where do I start?") and get:
  1. a short, warm response **drawn only from the books**,
  2. **chapter recommendations** as cards that deep-link into the right book + chapter,
  3. a **suggested listening plan** they can save (on their device).
- Available everywhere via a floating, brand-styled **"Guide me"** button.
- **No paid API key**; runs on free/open models via the owner's existing Cloudflare account.

## Non-goals (YAGNI)
- No user accounts / cross-device sync (device-local memory only).
- No in-browser model, no self-hosting.
- No general faith Q&A beyond the books; no non-KJV scripture.
- Not deployed to live (`main`) in this phase — preview/testing on `changev4` only.

## Decisions (from brainstorming, all confirmed)
| Topic | Decision |
|------|----------|
| Approach | Real AI chatbot (not a static decision tree) |
| Model host | **Cloudflare Workers AI** (open model, e.g. Llama) via binding — **no API key** |
| Grounding | **Strictly book content only**; **Bible refs = KJV only**; never invents teaching; redirects off-book questions |
| Retrieval | **Semantic search** — embed chapters → **Cloudflare Vectorize**; match reader's problem by meaning |
| Placement | Floating **"Guide me"** button on every page (landing + all players) |
| Memory | **Device-local** (localStorage): saved plan + recent chat |
| Abuse/cost | **Turnstile** bot check + per-visitor **rate limit** + reply/length caps + optional **daily cap** |

## Architecture
Static frontend → Cloudflare Pages Function → (Turnstile verify) → (rate limit) → Workers AI
embeddings → Vectorize query → assemble grounded prompt → Workers AI chat → shaped JSON reply.

### Components (clean boundaries)
| Unit | Path | Responsibility | Depends on |
|------|------|----------------|-----------|
| Chat endpoint | `functions/api/chat.js` | Orchestrate: verify Turnstile → rate-limit → embed → retrieve → prompt → call model → return `{reply, chapters[], plan?}` | env.AI, env.VECTORIZE, env.RATE_KV, env.TURNSTILE_SECRET, grounding map |
| Grounding helpers | `functions/api/_guide.js` | Prompt assembly (persona + hard rules + retrieved excerpts), KJV/scope guardrails, response shaping | grounding map |
| Grounding map | `functions/api/_chapters.json` (generated) | Compact `{id → {book, title, url, excerpt}}` for all tracks, bundled for fast excerpt lookup | built from `audiobook/data/**/chapters.json` |
| Ingest (one-time/rebuild) | `functions/api/ingest.js` (secret-gated route) | Reads `_chapters.json`, embeds each track (Workers AI `@cf/baai/bge-*`), upserts to Vectorize with metadata `{book,id,title,url}`. A Function route (NOT a local script) so it reuses the `AI`+`VECTORIZE` bindings — **no separate API token needed**. | env.AI, env.VECTORIZE |
| Frontend widget | `assets/guide.js` + `assets/guide.css` | Floating button, chat panel, Turnstile, chapter cards (deep-link), saved plan (localStorage), accessibility (large fonts, reduced-motion) | `/api/chat` |
| Wiring | `index.html`, `book-1..5.html` | Include the widget (one `<script>`/`<link>` + Turnstile script) | widget |
| Index builder | `audiobook/scripts/build_guide_index.py` | Generate `_chapters.json` from chapters.json (reuses existing data) | chapters.json |

### Models / bindings (decided, subject to availability confirmation at build time)
- Chat: an open instruct model on Workers AI (e.g. `@cf/meta/llama-3.3-70b-instruct-fp8-fast`).
- Embeddings: `@cf/baai/bge-base-en-v1.5` (768-dim) → Vectorize index dim 768, cosine.
- Bindings on the Pages project: `AI` (Workers AI), `VECTORIZE` (index), `RATE_KV` (KV), `TURNSTILE_SECRET` (env secret). Turnstile **site key** is public (frontend).

## Data flow
1. Reader opens panel → Turnstile issues a token.
2. Frontend POSTs `/api/chat` `{message, history[], turnstileToken}`.
3. Function verifies Turnstile (siteverify) → rejects if invalid.
4. Rate-limit check (KV sliding window per IP+session) → 429 + gentle message if exceeded.
5. Embed `message` (+ light history) → Vectorize query top-K (e.g. 6) tracks.
6. Look up those tracks' excerpts from `_chapters.json`; build system prompt: persona + HARD rules (book-only, KJV-only, no invention, redirect off-book, safety tone) + the excerpts + metadata.
7. Workers AI chat → parse into `{reply, chapters:[{book,id,title,url}], plan?:[{step,id,title}]}`.
8. Frontend renders reply + chapter cards (deep-link `book-N.html#<id>` / existing player anchor) + plan; saves plan + recent chat to localStorage.

## Grounding & safety rules (system prompt)
- Use ONLY the provided book excerpts; if the answer isn't in them, say so and point to what the books *do* cover. Never fabricate teaching or quotes.
- Any Bible reference must be **KJV**. Do not cite other translations or outside sources.
- Tone: gentle, pastoral, matches the books. **Not** medical/financial/clinical advice; for signs of crisis or self-harm, respond with compassion and gently encourage reaching out to a trusted person/professional or local emergency services (brief, non-clinical).
- Keep replies concise; always end toward a concrete next listen.

## Cost / abuse controls
- Turnstile gate on every call; per-visitor + per-IP rate limit (KV); max output tokens; max conversation turns; optional **daily request cap** → over-limit shows "the guide is resting, please try later."
- Workers AI free daily allowance covers light traffic; caps prevent runaway cost. No server-side storage of conversations (privacy); ephemeral logs only.

## Error handling
- Turnstile fail → friendly "please confirm you're human" retry.
- Model/timeout/over-cap → graceful fallback message + a static safe starting point (featured book / Book 1) so the reader is never stranded.
- Vectorize returns nothing relevant → bot says it plainly and offers the general starting point.

## Prerequisites the OWNER must enable (one-time, free tiers — I'll give exact steps)
1. Enable **Workers AI** on the Cloudflare account.
2. Create a **Vectorize** index (dim 768, cosine).
3. Create a **Turnstile** widget (site key + secret) for the site domain(s).
4. Add bindings to the Pages project: `AI`, `VECTORIZE`, `RATE_KV` (KV namespace), and `TURNSTILE_SECRET` env secret.
5. Run the one-time **ingest** to populate Vectorize from the books.
(My `turnstile-spin`, `wrangler`, and `cloudflare` skills cover the mechanics.)

## Build phases (single cohesive spec)
1. **Grounding index:** `build_guide_index.py` → `_chapters.json`; ingest → Vectorize.
2. **Backend:** `functions/api/chat.js` + `_guide.js` (retrieve → Workers AI → shaped reply). Test via curl/`wrangler pages dev`.
3. **Protections:** Turnstile verify + KV rate limit + caps.
4. **Frontend widget:** floating button, chat panel, chapter cards, saved plan, accessibility.
5. **Wiring:** include in `index.html` + `book-1..5.html`.
6. **Polish:** branding (gold/`.ceg`), reduced-motion, large-font, copy/safety wording.
7. **Verify on `changev4` preview** end-to-end.

## Testing / verification
- `wrangler pages dev` locally (with remote bindings) — sample problems ("grieving", "doubt", "where do I start") return **real** chapters, **KJV-only** refs, **no invented** content; deep links open the right chapter.
- Adversarial grounding tests (ask off-book / request non-KJV) → confirms redirect.
- Turnstile + rate-limit tests → endpoint rejects missing token + throttles.
- Cloudflare **preview deployment** for `changev4` (non-production branch) for full end-to-end — never `main`/live in this phase.

## Open questions
- None blocking. Exact Workers AI model IDs confirmed against current availability at build time; plan format (days vs. ordered list) finalized during frontend phase.
