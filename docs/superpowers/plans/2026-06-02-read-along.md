# Read-Along ("Listen + Read") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline,
> recommended for this UI-heavy feature) or superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax. The UI tasks are built with the **frontend-design**,
> **impeccable**, and **ui-ux-pro-max** skills.

**Goal:** A per-chapter reading view that highlights the spoken paragraph in sync with the
audio, shows the book's referenced diagrams inline, and is large-text / elderly-friendly.

**Architecture:** A build step computes per-paragraph start/end (from the cached clip
durations, same recipe the audio was assembled with) into small lazy-loaded
`readalong/<id>.json` files. The page gains a Read-along view that fetches that file,
renders role-styled paragraphs, and highlights/auto-scrolls on `timeupdate`. Diagrams are
extracted from the PDF and attached to paragraphs via a curated `data/diagrams.json`.

**Tech Stack:** Python 3.14 + `static_ffmpeg` (timings) and PyMuPDF/`fitz` (diagrams);
vanilla JS/CSS in the single-file `index.html`. Spec:
`docs/superpowers/specs/2026-06-02-read-along-design.md`. Branch: `changev1`.

**Convention:** no test framework in this repo — each script task verifies via an
assertion/print run; UI tasks verify via the local preview server + `preview_eval`.

---

### Task 1: `build_readalong.py` — timings for standalone tracks

**Files:** Create `audiobook/scripts/build_readalong.py`

- [ ] **Step 1: Timing helper.** Reuse the master assembly recipe: 300 ms lead-in, then
  for each segment its clip duration (`ffprobe`) + a trailing pause
  (`SCENE_GAP_MS` if `chapter_title` or last segment, else `master.pause_for(role)`).
  Build `paragraphs(seg_dir, seg_slice)` → list of `{role,text,start,end}` (seconds).
  Read clip durations with `build_manifest.duration_sec`.

```python
import json, io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C, master as M, build_manifest as BM

def paragraphs(seg_dir, seg_slice):
    out, t = [], 0.300            # 300ms lead-in
    n = len(seg_slice)
    for j, s in enumerate(seg_slice):
        f = seg_dir / s["file"]
        dur = BM.duration_sec(f) if f.exists() else 0.0
        start = t; t += dur
        out.append({"role": s["role"], "text": s["text"], "start": round(start,2), "end": round(t,2)})
        t += (C.SCENE_GAP_MS if (s["role"]=="chapter_title" or j==n-1) else M.pause_for(s["role"]))/1000.0
    return out
```

- [ ] **Step 2: Standalone-track build + self-check.** For one standalone track
  (`014-chapter-1-1`), build paragraphs from its own `out/segments/<id>/segments.json`,
  assert `paragraphs[-1]["end"]` within ±1.5 s of the manifest `durationSec`.

```python
def _selfcheck():
    man = {c["id"]: c["durationSec"] for c in json.load(io.open(C.ROOT.parent/"audio/book-5/manifest.json", encoding="utf-8"))["chapters"]}
    d = C.SEGMENTS / "014-chapter-1-1"
    segs = json.load(io.open(d/"segments.json", encoding="utf-8"))["segments"]
    ps = paragraphs(d, segs)
    print("014-chapter-1-1:", len(ps), "paras, end", ps[-1]["end"], "vs manifest", man["014-chapter-1-1"])
    assert abs(ps[-1]["end"] - man["014-chapter-1-1"]) < 1.5, "timing drift"
    print("OK")
if __name__ == "__main__": _selfcheck()
```

- [ ] **Step 3: Run** `cd audiobook/scripts && python build_readalong.py` → expect
  `OK` with end ≈ manifest duration. **Commit** `audiobook/scripts/build_readalong.py`.

---

### Task 2: `build_readalong.py` — split children + full generation

**Files:** Modify `audiobook/scripts/build_readalong.py`

- [ ] **Step 1: Iterate the final track list** (`chapters.json`) and emit one JSON per
  **playable** track. Standalone tracks (own `out/segments` dir) → `paragraphs(own,
  full)`. Split children (no own dir) → slice of the parent cache via
  `split_appendices.compute_parts` (same boundaries the audio used), timed from 0.
  Skip title-only split parents (they're collapsible headers). Output dir `readalong/`.

```python
import split_appendices as SP
def build_all():
    chapters = json.loads(io.open(C.CHAPTERS_JSON, encoding="utf-8").read())
    out_dir = C.ROOT.parent / "readalong"; out_dir.mkdir(exist_ok=True)
    diagrams = load_diagrams()                       # Task 3
    parent=None; parts=None; split_k=0; wrote=0
    sp_parents = SP_parents(chapters)                # level-1 followed by no-own-dir L2
    for t in chapters:
        if t["level"]==1: parent,parts,split_k = t,None,0
        own = C.SEGMENTS/t["id"]; has_own=(own/"segments.json").exists()
        if t["level"]==2 and not has_own: split_k += 1
        if t["id"] in sp_parents: continue           # title-only header, no reader
        if has_own:
            segs = json.loads(io.open(own/"segments.json", encoding="utf-8").read())["segments"]
            ps = paragraphs(own, segs)
        else:
            pdir = C.SEGMENTS/parent["id"]
            segs = json.loads(io.open(pdir/"segments.json", encoding="utf-8").read())["segments"]
            if parts is None:
                floor = SP.FLOOR_LONG if sum(SP.est_seg(s) for s in segs)>SP.LONG_TRACK_SEC else SP.FLOOR_SHORT
                parts = SP.compute_parts(segs, parent["title"], floor)
            s,e,_ = parts[split_k]; ps = paragraphs(pdir, segs[s:e])
        attach_images(t["id"], ps, diagrams)         # Task 3
        io.open(out_dir/f"{t['id']}.json","w",encoding="utf-8").write(json.dumps(
            {"id":t["id"],"title":t["title"],"paragraphs":ps}, ensure_ascii=False))
        wrote += 1
    print(f"wrote {wrote} readalong files")
```
(`SP_parents` = the split-parent detector added to `fix_scripture.py`; replicate the
3-line helper here.)

- [ ] **Step 2: Run + spot-check** a split child (`073-02-chapter-1`): its JSON exists,
  `paragraphs[-1].end` ≈ that child's manifest duration (±1.5 s). **Commit.**

---

### Task 3: Diagrams — extract + curate + attach

**Files:** Create `audiobook/scripts/extract_diagrams.py`, `data/diagrams.json`

- [ ] **Step 1: Extract candidates.** `extract_diagrams.py` opens the PDF, and for each
  image: skip if its xref repeats on >3 pages (decorative border/logo) or width<200px;
  save the rest to `images/book-5/diagrams/p<page>-<n>.jpg` and print
  `(page, w×h, size)`. (PyMuPDF `page.get_images` + `Document.extract_image`.)
- [ ] **Step 2: Run** `python extract_diagrams.py`; review the saved candidates against
  the ~15–20 in-text references (`grep -i "diagram\|picture below\|refer to appendix"`).
- [ ] **Step 3: Author `data/diagrams.json`** — for each real diagram, an entry
  `{"image":"images/book-5/diagrams/<f>.jpg","track":"<id>","after_text":"<unique snippet>"}`.
  Add `load_diagrams()` + `attach_images(track_id, paragraphs, diagrams)` to
  `build_readalong.py`: for each diagram whose `track`==id, find the paragraph whose
  `text` contains `after_text`, set its `image`; warn if 0 or >1 match.
- [ ] **Step 4: Re-run `build_readalong.py`**, confirm the targeted paragraphs now carry
  `image`. **Commit** scripts + `data/diagrams.json` + `images/book-5/diagrams/`.

---

### Task 4: Reader view — scaffold + role styling  *(frontend-design + ui-ux-pro-max)*

**Files:** Modify `index.html`

- [ ] **Step 1:** Add a `#reader` section (hidden by default) and a view-switch: choosing
  a ready chapter hides `#listen`, shows `#reader`, and plays it; a large **"← Chapters"**
  button reverses it. Reader contains: a header (chapter title + Back + **A− / A+**), a
  `#reader-body` paragraph container, and the existing docked player.
- [ ] **Step 2:** CSS for large, high-contrast reading (base `--reader-font:20px`,
  line-height ~1.8, max-width ~40rem centered) and **role styling**: `chapter_title`/
  `heading` as headings; `scripture` in a left-bordered quoted block; `decree` italic
  gold; `shekinaih`/`aaron` subtle speaker tint. `.speaking` = gold background tint +
  weight bump + smooth transition. Touch targets ≥44px. Use the existing palette.
- [ ] **Step 3:** Verify in preview: `preview_start book5-static`, open `#reader` via a
  selected chapter, screenshot — layout reads cleanly at desktop + 390px. **Commit.**

---

### Task 5: Reader view — render paragraphs + lazy-load  *(frontend-design)*

**Files:** Modify `index.html`

- [ ] **Step 1:** `openReader(i)`: `select(i,true)`, switch to `#reader`, then
  `fetch("readalong/"+id+".json")` (cache-first; embedded fallback not needed — http only).
  On success render each paragraph as `<p class="rpara role-<role>" data-start data-end>`;
  if `p.image`, append `<img class="rdiagram" src=...>` after it. On fetch failure show a
  gentle "Text view not available for this section yet" and keep the player working.
- [ ] **Step 2:** Wire the TOC rows to `openReader(i)` (replace the current `select` call
  for ready rows). Verify: opening 3 different chapters renders their text + any diagram.
  **Commit.**

---

### Task 6: Reader view — sync + tap-to-seek + lightbox + font control  *(impeccable)*

**Files:** Modify `index.html`

- [ ] **Step 1: Sync.** On `timeupdate` (throttled ~250ms), binary-search paragraphs for
  `start ≤ t < end`; toggle `.speaking`; `scrollIntoView({block:"center"})` (instant if
  `prefers-reduced-motion`). Only when `#reader` is visible.
- [ ] **Step 2: Tap-to-seek.** Click a `.rpara` → `A.currentTime = data-start; A.play()`.
- [ ] **Step 3: Lightbox.** Click `.rdiagram` → full-screen overlay (dark, centered,
  click/Esc to close, zoomable via CSS).
- [ ] **Step 4: Font control.** A−/A+ step `--reader-font` 16↔32px; persist in the
  existing `localStorage` state (`readerFont`); restore on load.
- [ ] **Step 5: Verify in preview** with `preview_eval`: highlight follows simulated
  `currentTime`, tapping a paragraph seeks, lightbox opens, A+ enlarges + persists across
  reload. Screenshot desktop + 390px + large-font. **Commit.**

---

### Task 7: Generate all + integrate + document

**Files:** generated `readalong/*.json`; Modify `AGENTS.md`

- [ ] **Step 1:** Run `build_readalong.py` for the full book; assert every playable track
  has a `readalong/<id>.json` and each passes the ±1.5 s end-vs-duration check (loop).
- [ ] **Step 2:** Add `readalong/` (commit the JSON — small, text-only) and confirm
  `.gitignore` does NOT exclude it.
- [ ] **Step 3:** End-to-end preview pass on `changev1`: play a chapter, read along,
  confirm a diagram appears at the right paragraph, elderly large-font is comfortable.
- [ ] **Step 4:** Document the read-along build + the `data/diagrams.json` curation in
  `AGENTS.md`. **Commit.** (Merge to `main` only on owner approval.)

---

## Self-Review

- **Spec coverage:** paragraph highlight (T6), auto-scroll (T6), tap-to-seek (T6),
  role styling incl. scripture block (T4), A−/A+ persisted (T6), lazy-load (T5), curated
  diagrams + lightbox (T3,T6), elderly large/high-contrast (T4), missing-file fallback
  (T5), file:// note (T5 comment), split-child timing (T2), verification ±1.5 s (T1,T2,T7).
  All spec sections map to a task. ✓
- **Placeholders:** none — scripts have full code; UI tasks specify structure, classes,
  and the sync algorithm concretely (visual polish is the design-skill execution layer).
- **Consistency:** `paragraphs()`, `compute_parts`, `pause_for`, `duration_sec`,
  `data-start/data-end`, `.speaking`, `--reader-font`, `readalong/<id>.json` used
  consistently across tasks.
