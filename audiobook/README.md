# Book 5 Audiobook — Pipeline & Runbook

Audiobook of **Behold My Messenger 5 — The Resurrection of the Dead** (~181k words,
91 tracks, ~20 hours). Free, neural multi-voice TTS → Audible-grade mastered MP3 →
static listening page.

## Voice cast (edge-tts, free)
| Role | Voice | Used for |
|---|---|---|
| Narrator | `en-GB-RyanNeural` | body of the book (the spine) |
| Heavenly Father | `en-US-BrianMultilingualNeural` (deep, −12%) | oracle decrees (wholly-quoted divine declarations) |
| Jesus | `en-GB-ThomasNeural` | scripture quotations |
| Shekinaih | `en-GB-SoniaNeural` | reflection prompts + decrees spoken *through* her |
| J Aaron K David | `en-US-AndrewMultilingualNeural` | passages attributed to his words |

Cast + rates/pitch + pronunciation lexicon + loudness targets all live in
`scripts/config.py`. Edit there.

## Pipeline
```
.docx ─► extract.py ─► data/chapters.json
        render.py  ─► out/segments/<track>/*.mp3   (one file per paragraph, per voice)
        master.py  ─► out/chapters/<track>.mp3  +  data/manifest.json
```

## Commands (run from audiobook/scripts/)
```bash
python extract.py                 # parse docx -> chapters.json (fast)
python render.py  --tracks 14     # pilot: render one track
python master.py  --tracks 14     # pilot: stitch + ACX loudness + manifest
python render.py                  # FULL render (overnight; resumable, skips done files)
python master.py                  # FULL master -> finished chapters + full manifest
```
Then publish audio + manifest to the site:
```bash
cp out/chapters/*.mp3      ../../audio/book-5/
cp data/manifest.json      ../../audio/book-5/manifest.json
```

## Listening page
`/book-5-audiobook.html` (project root). Standalone, brand-matched, no site chrome.
Fetches `audio/book-5/manifest.json`. Features: resume, ±15s, speed (0.85–1.3×),
sleep timer, localStorage progress, MediaSession lockscreen/Bluetooth controls,
keyboard (space / arrows), auto-advance.

## Mastering spec (verified on pilot)
EBU R128 two-pass loudnorm → **−19 LUFS integrated, −3 dBTP true-peak ceiling**,
70 Hz high-pass, 44.1 kHz mono, 128 kbps MP3. ACX/Audible compliant.
Pilot measured: −19.45 LUFS / −3.38 dBTP. ✔

## Hosting (full book)
~600–700 MB total. Recommended: Cloudflare R2 (10 GB free, **unlimited egress**) at
`audio.shekinaih-jaaronkdavid.com`; point the manifest `audioUrl`s there. Keep the
HTML page on Vercel. Do not commit the MP3s to git.

## Refining attribution
`scripts/extract.py` `role_for()` derives the speaker from structural cues
(paragraph style, wholly-quoted decrees, scripture refs, reflection labels) — never
from a name merely *mentioned* in narration. To hand-correct specific paragraphs,
add a `data/overrides.json` map of `{segment-key: role}` (hook is reserved in the
manifest builder).

## Dependencies
`pip install edge-tts python-docx static-ffmpeg pydub audioop-lts`
(ffmpeg is provided by static-ffmpeg — no system install / admin needed.)
