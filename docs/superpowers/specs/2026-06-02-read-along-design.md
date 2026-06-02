# Read-Along ("Listen + Read") — Design Spec

**Date:** 2026-06-02 · **Branch:** `changev1` · **Status:** approved, pre-implementation

## Goal

Let a listener **read the book's text while the audio plays** — the spoken paragraph
highlights and auto-scrolls, and the book's **diagrams/photos appear inline** at the
right place. Purpose: deeper comprehension; a calm, **elderly-friendly** reading
experience. Listening and reading reinforce each other.

## The experience (elderly-first "Read-along view")

Tapping a chapter in the TOC starts playback **and** opens a focused, full-width
reading screen (a view-switch within the single-page app — the TOC hides, the reader
shows; the player stays docked).

- **Large, high-contrast text**, generous line-height. An **A− / A+ control** changes
  the reading font size in steps; the choice is saved (localStorage) and reused.
- The **paragraph currently being spoken is highlighted** (soft gold tint, slightly
  larger weight) and **auto-scrolls to stay vertically centered**. The listener never
  loses their place.
- **Tap any paragraph → audio seeks to that paragraph's start** (easy navigation).
- **Referenced diagrams render inline** after the paragraph that references them; tap
  → full-screen lightbox (zoomable).
- Book **structure is preserved and styled by role**: headings, **scripture in a
  distinct quoted block**, oracle/decree styling, reflection prompts, etc.
- **Player stays docked** at the bottom (existing controls: play/pause, ±15s, speed,
  repeat — all large). A big **"← Chapters"** button returns to the TOC view.
- Respects `prefers-reduced-motion` (no auto-scroll animation; instant positioning).

## Architecture

Three independent pieces:

### 1. `build_readalong.py` → per-track timing+text JSON
For every **playable** final track (standalone tracks and split children; not the
title-only parents), emit `readalong/<track-id>.json`:

```json
{
  "id": "014-chapter-1-1",
  "title": "CHAPTER 1.1",
  "durationSec": 214.0,
  "paragraphs": [
    { "role": "chapter_title", "text": "CHAPTER 1.1", "start": 0.00, "end": 3.18 },
    { "role": "body", "text": "…", "start": 3.18, "end": 18.42,
      "image": "images/book-5/diagrams/app4-decree.jpg" },
    …
  ]
}
```

- `role` ∈ {chapter_title, heading, body, scripture, decree, shekinaih, aaron} — drives
  styling.
- `start`/`end` = seconds within that track's mastered MP3.
- `image` (optional) = a diagram to show after that paragraph.

**Timing computation (no forced alignment):** the mastered audio is just the per-segment
clips concatenated with role-based pauses (the recipe in `master.py`: 300 ms lead-in,
each clip, then `PAUSE_AFTER[role]` / `PARAGRAPH_GAP`, `SCENE_GAP` around chapter
open/close). `build_readalong.py` replays that recipe — `ffprobe` each segment clip for
its length, accumulate with the same pauses — so each paragraph's `start/end` matches
the audio timeline exactly. For **split children** it uses the same slice boundaries as
`split_appendices.py` (`compute_parts`), so a child's paragraphs are timed within the
child's own MP3 (starting at 0).

This runs in the 3.14 env (has `static_ffmpeg`); reuses `master.pause_for`,
`split_appendices.compute_parts`, and `config`.

### 2. Diagram extraction + placement (curated)
- `extract_diagrams.py`: pull candidate **content** images from the PDF (skip
  decorative ones — drop images that repeat across many pages, page borders, and very
  small images). Save to `images/book-5/diagrams/`.
- `data/diagrams.json`: a small list authored during a **curation pass**, each entry
  `{ "image": "images/book-5/diagrams/<f>.jpg", "track": "<track-id>", "after_text":
  "<unique snippet of the referencing paragraph>" }`. `build_readalong.py` finds the
  paragraph in `track` whose text contains `after_text` and sets its `image` field
  (logs a warning if no/2+ matches, so curation errors surface).
- Curation is semi-manual: the script proposes candidates + heuristic placements (via
  the PDF page→bookmark map and the ~15–20 in-text references); we eyeball/confirm.
  Auto page→paragraph matching is not reliable enough to ship unverified.

### 3. `index.html` — the Read-along view (frontend)
- A view-switch: `#toc` (browse) ↔ `#reader` (read-along). Selecting a ready chapter
  shows `#reader` and plays it. "← Chapters" shows `#toc`.
- **Lazy-load**: on open, `fetch("readalong/<id>.json")`; render paragraphs with
  role-based CSS. Only the opened chapter loads (keeps initial load light; the full
  1.3 MB text never loads up front).
- **Sync**: on `timeupdate`, binary-search the paragraph with `start ≤ t < end`; add
  `.speaking` to it (highlight + scale), remove from others, and `scrollIntoView`
  (centered, smooth unless reduced-motion). Throttle to ~4×/s.
- **Seek**: click/tap a paragraph → `A.currentTime = p.start`.
- **Images**: render `<img>` after the paragraph; click → lightbox overlay.
- **Font size**: `--reader-font` CSS var, A−/A+ buttons step it (e.g. 18→32 px),
  persisted in localStorage with the existing player state.

## Data flow
`chapters.json` + `out/segments/*` (clip durations) + `data/diagrams.json`
→ `build_readalong.py` → `readalong/<id>.json` (committed; small) → fetched lazily by
the Read-along view. Audio still streams from `AUDIO_BASE_URL` (R2); the page host is
unchanged.

## Scope
**In v1:** read-along text, paragraph-level highlight + auto-scroll, tap-to-seek,
role styling, A−/A+ sizing, curated diagrams inline + lightbox, elderly-friendly layout.
**Out (future):** word-by-word karaoke (needs forced alignment), text search,
multi-language, user highlights/notes.

## Edge cases / error handling
- **Missing `readalong/<id>.json`** (not built for a track): the reader shows the
  player + a gentle "Text view not available for this section yet" and still plays.
- **`file://`**: `fetch` of the JSON is blocked locally (same as the manifest). Read-along
  works on any HTTP host (the live site, the local preview server) — documented; not a
  regression for the deployed site.
- **Title-only parent tracks** (e.g. "APPENDIX 8"): they're collapsible headers, not
  opened in the reader; their children carry the read-along.
- **Paragraph with no speakable audio** (pure punctuation): zero-length span, skipped by
  the sync search.
- **Timing drift**: `start/end` are derived from the same recipe as the audio; verified
  by asserting the last paragraph's `end` ≈ the track's `durationSec` (±1 s) per track.

## Verification
- `build_readalong.py` self-check: for every track, `paragraphs[-1].end` within ±1 s of
  the manifest `durationSec`; paragraph count > 0; `start` monotonic.
- Live preview on `changev1`: open a chapter, confirm the highlight tracks the audio,
  auto-scroll centers, tap-to-seek works, a diagram renders + enlarges, A−/A+ resizes.
- Mobile widths (360/390) + a large-font pass for the elderly case.

## Files
- New: `audiobook/scripts/build_readalong.py`, `audiobook/scripts/extract_diagrams.py`,
  `data/diagrams.json`, `readalong/<id>.json` (generated), `images/book-5/diagrams/*`.
- Modified: `index.html` (reader view + sync + lightbox + font control), `AGENTS.md`
  (document the read-along build step).
