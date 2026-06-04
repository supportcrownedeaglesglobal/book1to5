# AGENTS.md — Book 5 Audiobook

Free, multi-voice audiobook of **Behold My Messenger 5 — The Resurrection of the Dead**
(Shekinaih Siew Sin Yap & J Aaron K David / Crowned Eagles Global). A single static
page streams ~21.3 h of neural-TTS narration, chapter by chapter, with an optional
**read-along reader view** (text scrolls + highlights as the voice speaks).

Narration is **Kokoro-82M** (Apache-2.0 weights + code — **free for commercial resale**,
which `edge-tts` is not). See *Voice cast* and *Pipeline* below.

## Repo layout

```
index.html                 # the whole site (standalone; embeds a manifest fallback)
audio/book-5/              # served audio: manifest.json + NNN-*.mp3  (mp3s are gitignored)
readalong/<id>.js          # per-track reader data (JSONP: assigns into RA_CACHE); committed
images/book-5/             # cover / back-cover (web-optimized)
images/book-5/diagrams/    # figures pulled from the PDF for the reader (extract_diagrams.py)
audiobook/
  scripts/                 # the production pipeline (see below)
  data/chapters.json       # source of truth: ordered tracks -> voiced segments
  data/manifest.json       # built catalog (mirrored to audio/book-5/manifest.json)
  data/versions.json       # per-chapter cache-bust versions (see Deployment)
  out/segments/<id>/       # per-segment TTS cache (one mp3 per segment) + segments.json
  out/chapters/<id>.mp3    # mastered per-track audio
docs/superpowers/specs/    # design specs
.venv-tts/                 # Python 3.12 + CUDA torch + kokoro (GPU render env; gitignored)
```

## Pipeline (run from `audiobook/scripts/`, Python)

1. `extract.py`  — parse the source `.docx` → `data/chapters.json`. New track at every
   Heading 1/2; each paragraph becomes a segment tagged with a speaker role.
2. **`render_kokoro.py`** — synthesize every segment with **Kokoro-82M** on the GPU
   (run in `.venv-tts`, Python 3.12 + CUDA torch). This is the **shipping, commercial-safe**
   voice. Resumable via `.kokoro_done` markers. `render.py` (edge-tts, no API key) is kept
   for quick dev previews only — its Microsoft voices are **not licensed for resale**, so
   never ship edge-tts audio. Both write `out/segments/<id>/<NNNN>-<role>.mp3`.
3. `master.py`   — stitch segments with breathing pauses, two-pass EBU R128 loudnorm
   to ACX spec (−19 LUFS / −3 dBTP), export 44.1 kHz mono 128k → `out/chapters/<id>.mp3`.
   (Master runs in the 3.14 env; it reads whatever mp3s the render step produced.)
4. `build_manifest.py` — build the full catalog manifest (every track listed; rendered
   ones playable, the rest marked `ready:false`) → `data/manifest.json`. Adds a per-track
   `version` from `data/versions.json` (cache-busting; see Deployment).
5. `inline_manifest.py` — embed the served manifest into `index.html` as a `file://`
   fallback (the page fetches `audio/book-5/manifest.json` first, falls back to the
   embedded copy when fetch is blocked). **Run this whenever the manifest changes.**
6. `build_readalong.py` — emit `readalong/<id>.js` for the reader view (see below).
   Run after any (re-)master so the text timings match the audio.
7. Staging: copy `data/manifest.json` → `audio/book-5/manifest.json` and the new
   `out/chapters/*.mp3` → `audio/book-5/`.

Source `.docx` and mastering targets are configured in `scripts/config.py`.
Python 3.14 (system) runs edge-tts/master/manifest/ffmpeg; `.venv-tts` (3.12) runs the
Kokoro GPU render. `master.py` reads the cache cross-env, so render in `.venv-tts` then
master in 3.14. Python 3.14 needs `audioop-lts` for pydub.

## Voice cast (assigned by structural cue, not name-mention)

Five roles — Narrator · Heavenly Father (deep) · Jesus · Shekinaih (female) ·
J Aaron K David — assigned per segment by structural role, not by who is named in the
text. The **shipping** role→voice map is `VOICE` in **`render_kokoro.py`** (Kokoro voices);
`config.py` `VOICES` holds the edge-tts equivalents used only for dev previews. Keep the two
maps role-aligned so a dev preview matches the shipping cast.

## Convention: split long audio into sub-parts per the PDF bookmarks

**Long tracks MUST be broken into navigable sub-parts that follow the book's own
section structure, as defined by the bookmarks of the Book 5 PDF**
(`Book_5_The_Resurrection_13July…CN(1).pdf`). A 4-hour single track is unusable; each
bookmarked sub-section should be its own track.

Implemented by **`audiobook/scripts/split_appendices.py`** (splits any long section,
not only appendices):

- **Re-groups already-rendered segment audio** at the manuscript's sub-headings — which
  mirror the PDF bookmarks — and re-masters each sub-part. **No re-synthesis** (the
  segment cache in `out/segments/` is reused), so it is fast and lossless.
- Each split track becomes a **title-only level-1 parent** + **level-2 children** (the
  site TOC renders a level-1-with-children as a collapsible header, so the parent must
  hold no audio or it would be unreachable). The audio TOC is two levels only; deeper
  PDF nesting (L3/L4) flattens into level-2 children.
- **Adaptive granularity floor**: long tracks (>10 min) use a 90 s floor so they don't
  shatter into hundreds of fragments; short tracks use 20 s so they still split per
  their bookmarks. Page-reference bookmarks like "(page 376 to 377)" are not cut points.
- **Idempotent + resumable**: already-split parents are title-only (~seconds) so a
  re-run skips them; a child mp3 already produced is reused.

Usage:
```
python split_appendices.py --dry     # print the planned split, change nothing
python split_appendices.py --only N  # split only the track with order N (pilot)
python split_appendices.py           # split all level-1 tracks from Appendix 1 onward
python inline_manifest.py            # then refresh the embedded manifest in index.html
```

Note: the audio was rendered from the **22 Dec `.docx`**; the **13 July PDF** is the
bookmark reference. They align closely, but a section that the docx did not tag as a
heading cannot be split from the audio without re-rendering from the newer source.

## Convention: read Bible references in full

Abbreviated scripture references **MUST be narrated in full form**:

- `Isa 6:1` → "Isaiah chapter 6 verse 1"
- `1 PETER 5:5-6` → "First Peter chapter 5, verses 5 to 6"
- `Psa 19:12` → "Psalm 19, verse 12" (Psalms are spoken without "chapter")

This is a render-time text transform (the display text in `chapters.json` is left
abbreviated). `scripture.expand()` in `audiobook/scripts/scripture.py` holds the
book-abbreviation map (handling inconsistent forms in the manuscript: `Psa`/`Ps`,
`Mat`/`Matt`/`MATHEW`, `Joh`/`John`, `1Co`/`1Cor`, full UPPERCASE names, etc.).
`render.py` applies it after the pronunciation lexicon, so every future render
expands references automatically. Whenever the abbreviation map changes, re-render
the affected segments with `fix_scripture.py` (re-synthesizes only the segments whose
text changes, then re-masters only the affected tracks/children).

**Divine pronouns — read short ALL-CAPS words as words, not letters.** The manuscript
writes divine pronouns in capitals ("MY", "US", "WE", "OUR", …). Short all-caps words get
**spelled out letter-by-letter** by the TTS — "MY" → "M-Y", "US" → "U-S" (e.g. "BEHOLD MY
MESSENGER" was heard as "behold M-Y messenger"). Fix by respelling each to the lowercase word
in `config.py` `LEXICON`: `"US": "us"`, `"MY": "my"`. The match is `\bWORD\b` and
case-sensitive, so it leaves "JESUS"/"ARMY"/"MYSTERY"/already-lowercase forms alone.

**After adding a lexicon entry you MUST re-render with Kokoro, never edge-tts.**
`fix_scripture.py`'s own re-synthesis path uses edge-tts — off-voice AND not commercial-safe —
so it would silently reintroduce the wrong voice for those segments. The correct three steps:

```
# 1. re-render ONLY the matching segments with Kokoro (.venv-tts) — re-applies the new lexicon
.venv-tts/Scripts/python render_kokoro.py --pattern '\bMY\b'
# 2. re-master the affected tracks + rebuild & inline the manifest (3.14 env) — NO re-synthesis
python fix_scripture.py --pattern '\bMY\b' --remaster-only
# 3. python build_readalong.py (refresh timings) · bump the changed tracks in data/versions.json ·
#    re-upload those mp3s to R2 (they're gitignored; the live site streams from the bucket)
```

## Read-along reader view

The player has a second mode (toggle → `body.reading`) that shows the book text in large
type and highlights the spoken paragraph as the audio plays — "listen and read at the same
time", built for elderly readers. It is **paragraph-level** sync with **no forced
alignment**: `build_readalong.py` replays `master.py`'s exact assembly timeline (300 ms
lead-in + each segment's measured clip duration + the same role/scene pauses) to compute a
`start`/`end` for every paragraph, and writes `readalong/<id>.js` — a one-line JSONP wrapper
`(window.RA_CACHE=window.RA_CACHE||{})["<id>"]={id,title,paragraphs:[{role,text,start,end,image?}]}`.
The reader lazy-loads it with a `<script>` tag — NOT `fetch`, because browsers block `fetch`
of local files over `file://`, but a `<script src>` tag-load works there (the same reason the
audio and the embedded-manifest fallback work when index.html is opened directly). It is keyed
in `RA_CACHE` (loaded once), and on `timeupdate` the reader finds
the paragraph where `start ≤ t < end`, tints it gold, and scrolls it to center. Tap a
paragraph to seek; tap a diagram to open the lightbox; A−/A+ sets reader font (persisted).
At track end the reader **auto-advances** to the next chapter (continuous play) unless
repeat-one is on.

- Split children are timed within their **own** mp3 (the same parent-cache slice
  `split_appendices.py` used); title-only split parents get no reader file.
- **Diagrams/figures** come from the PDF in two scripted steps, then attach automatically:
  `extract_diagrams.py --pdf <book5.pdf>` pulls content images (skips decorative/duplicate/
  tiny) into `images/book-5/diagrams/`; `place_diagrams.py --pdf <book5.pdf>` auto-authors
  `data/diagrams.json` (`{image, track, after_text}`) — it maps each image to a track by
  **IDF-weighted** page↔narration word matching (rare names like "Davidis" decide it; robust
  to the Dec-docx vs Nov-PDF divergence), then to a paragraph within that track. `--groups`
  picks which figure families to place — default **`A,D`** (core diagrams + photos), skipping
  the ~120 testimony screenshots (B) and text-page captures (C) that just duplicate the
  narration. Run with `--dry` first to sanity-check placement; prune unreferenced image files
  after a group change to keep the repo lean. `build_readalong.attach_images` then binds each
  figure to the paragraph holding its unique `after_text`; **several figures may stack on one
  paragraph** (a run of testimony screenshots), so a paragraph carries an `images` list. The
  file is optional; absent = text-only. (`_diagram-gallery.html`, gitignored, is a local
  review grid of all candidates.)
- **Always re-run `build_readalong.py` after a (re-)master** — its timings are derived from
  the current segment durations, so stale audio ⇒ drifting highlights. It self-checks every
  track's last `end` against the manifest duration and flags any >1.6 s drift.

```
python build_readalong.py            # regenerate all readalong/<id>.js
python build_readalong.py --check    # verify timing on one track, then exit
```

## Deployment

Live via **GitHub Pages** at <https://supportcrownedeaglesglobal.github.io/book5/>
(Deploy-from-branch: `main` / root). The repo is **public** (free-plan Pages requires
it). `index.html` works offline / over `file://` thanks to the embedded manifest.

**Audio hosting (Cloudflare R2):** the `.mp3` files are gitignored (too large for the
repo), so the audio is served from a CDN with free egress — **Cloudflare R2**. The
audio base URL is a single constant in `index.html`:

```js
const AUDIO_BASE_URL = "https://pub-<id>.r2.dev/beholdmymessenger-book5";  // R2 bucket URL + the folder the mp3s are in ("" = same-origin/local)
```

It points at the R2 **public bucket URL + the folder the mp3s live in** (book 5's mp3s were
uploaded to `…/beholdmymessenger-book5/`, flat). So `audioSrc()` takes just the **filename**
from each manifest `audioUrl` and appends it: `${AUDIO_BASE_URL}/<id>.mp3?v=<version>` — change
the host/folder in this one place, no manifest regen. (With `AUDIO_BASE_URL=""`, local/same-origin
keeps serving the mp3s from `audio/book-5/`.) A **custom domain** can replace the `pub-*.r2.dev`
host later for edge-caching. Upload with `audiobook/scripts/upload_r2.sh` (`BUCKET=… bash upload_r2.sh`), which
sets `Cache-Control: public, max-age=31536000, immutable` so repeat plays hit Cloudflare's
edge (free). **Caching only works via a custom domain — the `pub-*.r2.dev` URL does NOT
cache.** Verify with the response header `cf-cache-status: HIT`. The static page can stay on
GitHub Pages, or move to **Cloudflare Pages** (free, no commercial-use restriction) to keep
site + audio under one Cloudflare account/domain.

**Cache-busting a single chapter** (because `immutable` tells the CDN to cache for a year):
the site loads every track through `audioSrc(c)`, which appends `?v=<version>`. To push a
re-recorded chapter: (1) re-master + re-upload that one `.mp3` to R2, (2) bump its number
in `data/versions.json` by 1, (3) `python build_manifest.py && python inline_manifest.py`,
redeploy. Unlisted chapters default to `version: 1`. The `?v=` change makes the browser and
edge treat it as a new URL — only that chapter re-downloads.

## Gotchas

- Global git identity is `jjcheng9296` — do **not** pass `-c user.name` (impersonation).
- `gh` CLI is not installed; the repo was created on github.com.
- The page deliberately overrides any "no gradient / no gradient-text" brand bans
  (owner asked for the vivid metallic "throne-room" look).
- **Split children can go stale after a re-render.** `split_appendices.master_slice`
  skips a child whose mp3 already exists (resume cache), so a global voice/text change
  re-renders the parent's *segments* but leaves the children mastered from the *old* audio.
  After any such change, re-master the children explicitly:
  `python fix_scripture.py --remaster-only --children-only` (it sets `SP.FORCE = True`).
  Symptom if missed: read-along highlights drift on split sub-parts only.
- **Never re-run `split_appendices.py` on an already-split `chapters.json`** — it would
  split the children again and duplicate tracks. Split once from the monolithic manifest;
  to redo, `git checkout audiobook/data/chapters.json` first.
