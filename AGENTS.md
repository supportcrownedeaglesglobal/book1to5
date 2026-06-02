# AGENTS.md — Book 5 Audiobook

Free, multi-voice audiobook of **Behold My Messenger 5 — The Resurrection of the Dead**
(Shekinaih Siew Sin Yap & J Aaron K David / Crowned Eagles Global). A single static
page streams ~20.6 h of neural-TTS narration, chapter by chapter.

## Repo layout

```
index.html                 # the whole site (standalone; embeds a manifest fallback)
audio/book-5/              # served audio: manifest.json + NNN-*.mp3  (mp3s are gitignored)
images/book-5/             # cover / back-cover (web-optimized)
audiobook/
  scripts/                 # the production pipeline (see below)
  data/chapters.json       # source of truth: ordered tracks -> voiced segments
  data/manifest.json       # built catalog (mirrored to audio/book-5/manifest.json)
  out/segments/<id>/       # per-segment TTS cache (one mp3 per segment) + segments.json
  out/chapters/<id>.mp3    # mastered per-track audio
docs/superpowers/specs/    # design specs
```

## Pipeline (run from `audiobook/scripts/`, Python)

1. `extract.py`  — parse the source `.docx` → `data/chapters.json`. New track at every
   Heading 1/2; each paragraph becomes a segment tagged with a speaker role.
2. `render.py`   — synthesize every segment with `edge-tts` (no API key) into
   `out/segments/<id>/<NNNN>-<role>.mp3`. **Resumable** (skips existing files).
3. `master.py`   — stitch segments with breathing pauses, two-pass EBU R128 loudnorm
   to ACX spec (−19 LUFS / −3 dBTP), export 44.1 kHz mono 128k → `out/chapters/<id>.mp3`.
4. `build_manifest.py` — build the full catalog manifest (every track listed; rendered
   ones playable, the rest marked `ready:false`) → `data/manifest.json`.
5. `inline_manifest.py` — embed the served manifest into `index.html` as a `file://`
   fallback (the page fetches `audio/book-5/manifest.json` first, falls back to the
   embedded copy when fetch is blocked). **Run this whenever the manifest changes.**
6. Staging: copy `data/manifest.json` → `audio/book-5/manifest.json` and the new
   `out/chapters/*.mp3` → `audio/book-5/`.

Source `.docx` and mastering targets are configured in `scripts/config.py`.
Python 3.14 needs `audioop-lts` for pydub.

## Voice cast (assigned by structural cue, not name-mention)

Narrator = Ryan · Heavenly Father = Brian (deep) · Jesus = Thomas ·
Shekinaih = Sonia · J Aaron K David = Andrew. See `config.py` `VOICES`.

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

**Divine pronouns:** the manuscript writes divine pronouns in capitals ("US", "WE",
"OUR"). The acronym-like ones must be spoken as words, not spelled out — notably
**"US" reads as "us", never "U-S"**. This is a pronunciation-lexicon entry in
`config.py` (`"US": "us"`; `\bUS\b` leaves "JESUS"/"THUS"/"U.S." alone). After adding
a lexicon entry, re-render the affected segments with the general form of the fix
tool, which targets any raw-text pattern and re-applies the full pipeline:
`python fix_scripture.py --pattern '\bUS\b'`.

## Deployment

Live via **GitHub Pages** at <https://supportcrownedeaglesglobal.github.io/book5/>
(Deploy-from-branch: `main` / root). The repo is **public** (free-plan Pages requires
it). `index.html` works offline / over `file://` thanks to the embedded manifest.

**Audio hosting (Cloudflare R2):** the `.mp3` files are gitignored (too large for the
repo), so the audio is served from a CDN with free egress — **Cloudflare R2**. The
audio base URL is a single constant in `index.html`:

```js
const AUDIO_BASE_URL = "";   // "" = same-origin; set to your R2 custom domain (no trailing slash)
```

Set it to the R2 **custom domain** (e.g. `https://cdn.yourdomain.com`) and every track
loads from `${AUDIO_BASE_URL}/audio/book-5/<id>.mp3` (the manifest keeps relative
`audioUrl`s; `audioSrc()` prepends the base — change the domain in one place, no manifest
regen). Upload with `audiobook/scripts/upload_r2.sh` (`BUCKET=… bash upload_r2.sh`), which
sets `Cache-Control: public, max-age=31536000, immutable` so repeat plays hit Cloudflare's
edge (free). **Caching only works via a custom domain — the `pub-*.r2.dev` URL does NOT
cache.** Verify with the response header `cf-cache-status: HIT`. The static page can stay on
GitHub Pages, or move to **Cloudflare Pages** (free, no commercial-use restriction) to keep
site + audio under one Cloudflare account/domain.

## Gotchas

- Global git identity is `jjcheng9296` — do **not** pass `-c user.name` (impersonation).
- `gh` CLI is not installed; the repo was created on github.com.
- The page deliberately overrides any "no gradient / no gradient-text" brand bans
  (owner asked for the vivid metallic "throne-room" look).
