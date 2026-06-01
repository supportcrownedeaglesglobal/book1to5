# Behold My Messenger 5 — The Resurrection of the Dead · Audiobook

A free, single-purpose listening site for **Behold My Messenger 5 — The Resurrection
of the Dead** by Shekinaih Siew Sin Yap & J Aaron K David. A Crowned Eagles Global work.

- **`index.html`** — the landing + listening page (cover hero, full table of contents,
  persistent player with resume, ±15s, speed, sleep timer, lockscreen controls).
- **`images/book-5/`** — front and back cover art.
- **`audio/book-5/manifest.json`** — chapter catalog the page reads (durations, order,
  ready state). The MP3s themselves are hosted on object storage, not committed here.
- **`audiobook/`** — the offline production pipeline that builds the audio.

## Audio pipeline (`audiobook/`)
`.docx → extract.py → chapters.json → render.py (edge-tts, 6-voice cast) →
master.py (EBU R128 / ACX loudness) → build_manifest.py`. Full runbook in
[`audiobook/README.md`](audiobook/README.md).

## Voice cast
Narrator (body) · Heavenly Father (decrees) · Jesus (scripture) · Shekinaih
(reflections) · J Aaron K David (attributed speech).

## Hosting
The site is static. Host the page anywhere; serve the ~1 GB of MP3s from object
storage with range-request support (Cloudflare R2 recommended — free, unlimited egress)
and point the manifest `audioUrl`s at that bucket.
