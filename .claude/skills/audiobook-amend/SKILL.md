---
name: audiobook-amend
description: >-
  Amend the "Behold My Messenger" multi-voice audiobook (Books 1-5) and publish it live.
  Use for ANY change to the audio, text, pronunciation, PDF hyphenation, diagrams/figures, or
  the read-along reader — e.g. re-voice a role, fix wording, add/fix a figure, fix read-along
  sync — and for deploying those changes live to Cloudflare Pages + R2.
---

# Behold My Messenger — Audiobook Amendment & Deploy

Runbook for changing the audiobook and shipping it live. Scripts live in `audiobook/scripts/`.
Read §0 and §1 before touching anything.

## 0. Architecture & invariants
- **Static site**, no build step: `index.html` + `book-1.html`..`book-5.html`. Audio is on **Cloudflare R2**; read-along data is JSONP in `readalong/`. Served by **Cloudflare Pages from the `main` branch**.
- **Per-book selection = `BMM_BOOK` env var (1..5, default 5).** **Book 5 is FLAT** (`audio/book-5/`, `readalong/`, `audiobook/data/`). **Books 1-4 NEST** under `book-N/` (`audio/book-N/`, `readalong/book-N/`, `audiobook/data/book-N/`).
- **Two Python environments:**
  - `.venv-tts` (GPU; torch + kokoro; 24 kHz synthesis) — **only** for `render_kokoro.py`.
  - `C:\Python314\python.exe` (base; pydub + static_ffmpeg; 44.1 kHz mastering) — everything else.
- **Voice cast** is the `VOICE` map in `render_kokoro.py` (the production one — *not* `config.py` VOICES):
  `chapter_title/heading/body → bm_george (b)`, `scripture → bm_daniel (b, "Jesus")`,
  `decree → am_fenrir (a, "Father")`, `shekinaih → af_heart (a)`, `aaron → am_michael (a)`.
  lang `a`=American, `b`=British. Default fallback `bm_george (b)`.
- **Branches:** **`changev3` is the deploy/live line** — commit fixes here and push to `main`; Cloudflare serves it. **`changev4` is local feature-testing only — do NOT deploy from it.**
- **Endpoints:** live domain `https://crownedeaglesglobal-beholdmymessengerseries-audio.com`; R2 public `https://pub-163ec17fb5564d7a9193345f48fea08f.r2.dev/beholdmymessenger-book{N}/`; R2 bucket `crownedeaglesglobal-beholdmymessenger-series`. Source PDFs: `C:\Users\jda61\OneDrive\Desktop\5books26Dec\`.

## 1. SAFETY — non-negotiable
1. **Never type a secret / API key / token into any field.** R2 auth is `wrangler login` (browser OAuth) — there is no key to paste, ever. If anything asks for a secret, stop and have the user do it.
2. **Never run the GPU render (`render_kokoro`) at the same time as ffmpeg (`master`/`apply_voice_fix`) or heavy spawns (Workflows, large Grep sweeps, multiple agents).** On this Windows box that contention hard-kills ffmpeg (`0xC0000142`). `revoice.py` enforces strict sequence. While a render/ffmpeg job is running, do **read-only** work only; to wait on it, block with `TaskOutput(block=true)` (spawns nothing). Run renders **alone**.
3. **Deploy order: R2 FIRST, manifest SECOND.** `publish_audio` uploads the new mp3s to R2 *before* you push the manifest, so a user never gets a new manifest pointing at stale audio.
4. **Cache-bust is automatic** and must stay so: `publish_audio` bumps `?v=` in `versions.json`; `_headers` makes HTML/manifests/read-along `must-revalidate` while R2 audio is 1-year `immutable`. This is what stops old phones from hearing the old version — don't remove it.
5. **mp3s are gitignored.** Never commit audio; R2 is the host. Commit only HTML, manifests, read-along, `audiobook/data`, and scripts.

## 2. Common amendments — pick the one that fits

### A. Re-voice a role (change a narrator voice)
1. Edit the `VOICE` map in `audiobook/scripts/render_kokoro.py`.
2. `C:\Python314\python.exe audiobook/scripts/revoice.py --books <N...> --roles <role...>`
   — render (GPU) → re-master affected tracks only → read-along → stage → inline, strictly sequential. **Run alone.** Background it and wait with `TaskOutput(block=true)`.
3. Publish (§4): one book `BMM_BOOK=N C:\Python314\python.exe audiobook/scripts/publish_audio.py`; Books 1-4 rollout `C:\Python314\python.exe audiobook/scripts/publish_revoiced.py` (it auto-detects decree/shekinaih tracks — **update its `EXPECT` counts** for a new rollout).

### B. Fix pronunciation or wording
- **Pronunciation:** add the substitution to the lexicon in `config.py`, then `BMM_BOOK=N .venv-tts python render_kokoro.py --pattern '<regex>'` (GPU, alone) → `apply_voice_fix.py` (or re-master) → publish.
- **Wording:** edit `audiobook/data[/book-N]/chapters.json`, then `render_kokoro.py --only <track-id>` (GPU) → re-master that track → rebuild (§3) → publish.

### C. Fix PDF line-break hyphenation (e.g. "YAH- WEH", "Denomina- tion")
- `C:\Python314\python.exe audiobook/scripts/fix_text_data.py --dry` (inspect joins) then without `--dry`.
  Joins `letter- letter` ("ma- keth"→"maketh"); KEEPS real compounds ("Anti-Christ") and verse ranges ("10:1- 2"→"10:1-2", never "10:12"). `build_readalong._dehyph` applies the same at display time.
- Then rebuild read-along (§3).

### D. Add or fix diagrams/figures
1. Extract candidates: `BMM_BOOK=N python extract_diagrams.py --pdf "<Book N PDF>" --contact` (writes `images/book-N/diagrams/` + contact sheets). Curate.
2. Place: `BMM_BOOK=N python place_diagrams.py --pdf "<Book N PDF>" --groups A,D,BC --merge`
   (`--merge` = add new images only, keep existing; `--groups A,D,BC` = include back-matter/testimonies; default `A,D` skips them).
3. **Ambiguous anchor** (figure whose after_text is a heading repeated in the track): `BMM_BOOK=N python fix_ambiguous_occ.py "<Book N PDF>"` — sets an `occ` index; `build_readalong` honors it so the figure lands on the intended occurrence.
4. Rebuild read-along (§3) and verify with `verify_attached.py` + `verify_order.py`.

### E. Read-along sync / figure order only (no audio change)
- `BMM_BOOK=N C:\Python314\python.exe audiobook/scripts/rebuild_text_one.py` (manifest → stage → read-along → inline).

## 3. Build pipeline (per book; no audio change)
**Order matters — each step consumes the previous:**
`build_manifest.py → stage_web.py → build_readalong.py → inline_manifest.py`.
`rebuild_text_one.py` runs all four for one book. (After audio changes, `revoice.py`/`apply_voice_fix.py` handle the master step first.)

## 4. Publish to R2 + deploy live
1. `BMM_BOOK=N python publish_audio.py` (auto-detects mp3s changed since `.last_publish`; or `--changed <ids>` / `--all` / `--dry` / `--no-upload`). For Books 1-4: `publish_revoiced.py`. This bumps `?v=`, rebuilds the manifest, re-inlines `book-N.html`, and uploads changed mp3s to R2 via wrangler.
2. On **`changev3`**: `git add -A` (confirm `0` mp3 staged) `&& git commit && git push origin changev3 && git push origin changev3:main`. Cloudflare auto-builds from `main` (~1-3 min).

## 5. Verify (always run after a change)
- **Local:** `verify_attached.py` (every figure attaches), `verify_order.py` (0 page-order inversions), `verify_revoiced.py` or the `build_readalong` drift line (read-along within 1.6 s of audio), `check_ambiguous.py`, `check_images.py`.
- **Live** (needs network — run the Bash/PowerShell tool with the sandbox **disabled**): `verify_live.py` (deployed manifests byte-match local + every re-voiced track on R2 with matching size), `check_images_live.py` (all images HTTP 200 + size), `verify_live_order.py`, `verify_live_figures.py`.
- **Cloudflare lag:** the live edge updates ~1-3 min after the push. When diffing a live file vs local, **normalize line endings first** (`tr -d '\r\n'`): git's LF↔CRLF leaves a 1-byte difference that is NOT a real change — don't chase it.

## 6. Script reference
| Script | Run | Does |
|--------|-----|------|
| `render_kokoro.py` | `.venv-tts python … [--only T] [--pattern RE] [--role R…]` | GPU TTS into `out/segments/`; `--role`/`--pattern` ignore the `.kokoro_done` resume marker |
| `master.py` | `python … [--tracks N]` | Assemble segments → ACX-loudness chapter mp3 + manifest |
| `split_appendices.py` | `python … [--dry] [--only ORDER]` | Split long tracks at sub-headings into level-2 children (no re-synth) |
| `revoice.py` | `C:\Python314\python.exe … --books N… --roles R…` | Full re-voice (render→remaster→readalong→stage→inline), sequential, local-only |
| `apply_voice_fix.py` | `BMM_BOOK=N python … --roles R… [--check]` | Re-master only tracks containing a re-voiced role + refresh manifest |
| `build_manifest.py` / `stage_web.py` / `build_readalong.py` / `inline_manifest.py` | `BMM_BOOK=N python …` | The 4-step web build (run in this order) |
| `rebuild_text_one.py` | `BMM_BOOK=N python …` | All 4 build steps for one book after a text/data edit |
| `publish_audio.py` | `BMM_BOOK=N python … [--changed…|--all|--dry|--no-upload]` | Bump `?v=`, rebuild manifest, inline, upload changed mp3s to R2 |
| `publish_revoiced.py` | `python … [book#…]` | Per-book publish of the decree/shekinaih re-voice (verifies counts vs `EXPECT`) |
| `extract_diagrams.py` | `BMM_BOOK=N python … --pdf "<pdf>" [--contact]` | Extract+curate candidate figures (never edits diagrams.json) |
| `place_diagrams.py` | `BMM_BOOK=N python … --pdf "<pdf>" [--groups A,D,BC] [--merge]` | Map figures → track+paragraph anchor |
| `fix_text_data.py` | `python … [--dry]` | De-hyphenate chapters.json + diagram anchors (all books) |
| `fix_ambiguous_occ.py` | `BMM_BOOK=N python … "<pdf>"` | Set `occ` on figures with a repeated anchor |
| `verify_*.py` / `check_*.py` | `python …` (iterate all books) | Verification (see §5) |
| `make_player.py` | `BMM_BOOK=N python … [--audio-base URL]` | Regenerate `book-N.html` (1-4) from the `book-5.html` template |

## 7. Gotchas (hard-won)
- **Split-children read-along timing** tiles the parent's cached segments by *stored* segment counts — never recompute split boundaries inside `build_readalong` (it drifts and desyncs text from audio; this caused the Appendix-8 bug).
- **`occ`** is required when a figure's after_text is a heading repeated in its track (e.g. "THE MODUS OPERANDI OF THE TRINITY", "THE TRINITY") — otherwise it attaches to the first occurrence. `fix_ambiguous_occ.py` sets it.
- **`publish_revoiced.py` `EXPECT` counts are per-rollout** — update them or it falls back to `--all`.
- **`inline_manifest.py`** needs the `<script>\nconst M_URL` anchor present in the player HTML; it escapes `</script>` in titles so a title can't break out of the JSON block.
- **Loudnorm** bypasses linear mode on near-silent tracks (input_i ≤ −70 dB) to avoid `offset=inf` silently dropping a chapter.
- Windows console is cp1252; publish scripts reconfigure stdout to utf-8 so wrangler's emoji output doesn't crash them.

## See also
- `audiobook/AGENTS.md` — the split-per-bookmarks convention and pipeline notes.
- Memory: `render-contention.md` (the GPU+ffmpeg contention lesson), `book-5-audiobook.md`.
