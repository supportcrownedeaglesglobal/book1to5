"""
split_appendices.py — Break long appendix tracks into navigable sub-parts by
re-grouping the already-rendered segment audio at the book's own sub-headings.

NO re-synthesis. Every segment was rendered once by render.py and cached at
out/segments/<track-id>/<NNNN>-<role>.mp3. This script re-concatenates contiguous
slices of those cached clips (with the same breathing pauses) and re-masters each
slice with the existing two-pass loudnorm, producing one MP3 per sub-part.

Split rule (matches the user's "sub-headings only" choice):
  * Only appendices longer than SPLIT_THRESHOLD_SEC are split.
  * Cut points are the real sub-headings (role == "heading"), excluding page
    references like "(page 376 to 377)".
  * A sub-part shorter than MIN_PART_SEC is merged forward into the next cut, so a
    run of tiny headings (e.g. a bulleted "benefits" list) never yields sliver
    tracks. This is a sanity floor, NOT the long-part time-cap that was declined.

The first sub-part keeps the appendix's own id/order and stays level 1 (the section
header + intro); the rest become level-2 children, so the existing TOC renders each
appendix as a collapsible part with nested chapters.

Usage (run from audiobook/scripts):
  python split_appendices.py --dry        # print the planned split, touch nothing
  python split_appendices.py --only 70    # split just one appendix (by order), pilot
  python split_appendices.py              # split all long appendices, rebuild manifest, stage
"""
import argparse, json, re, shutil, tempfile, sys
from pathlib import Path
import config as C
import master as M
from pydub import AudioSegment

PAGEREF = re.compile(r"^\(?\s*page\b", re.I)
FIRST_ORDER   = 63       # APPENDIX 1 — only split it and everything after (back matter)
TARGET_MIN_SEC = 60      # ignore tracks shorter than this (and title-only split parents)
LONG_TRACK_SEC = 600     # tracks longer than this use the coarse floor
FLOOR_LONG    = 90       # sub-part floor for long tracks (avoid hundreds of fragments)
FLOOR_SHORT   = 20       # sub-part floor for short tracks (still split per bookmarks)
WPS           = 138 / 60.0  # rough words/sec, only used to size sub-parts

WEB_AUDIO = C.ROOT.parent / "audio" / "book-5"   # where the site serves audio + manifest


def est_seg(seg):
    return len(seg["text"].split()) / WPS + C.PAUSE_AFTER.get(seg["role"], C.PARAGRAPH_GAP_MS) / 1000.0


def slugify(t):
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return t[:48].rstrip("-") or "part"


def compute_parts(segs, parent_title, min_sec):
    """Return [[start, end, title], ...].

    If there is nothing worth splitting on, returns a single part (the whole
    track, unchanged). Otherwise the first part is a TITLE-ONLY level-1 parent
    (segment 0, the spoken "APPENDIX N") and the rest are level-2 children that
    tile every remaining segment — so no audio is ever stranded under a
    non-playable collapsible header.

    Children are cut at every real sub-heading (role == "heading", excluding page
    refs); any child shorter than min_sec is merged BACKWARD into the previous kept
    child. Backward (not forward) merge is essential: a run of tiny headings (e.g. a
    bulleted list) folds into the section above, never swallows the next big section
    and mis-titles it. min_sec is adaptive (small for short tracks so they still
    split per their bookmarks, larger for long tracks to avoid over-fragmenting)."""
    cuts = [i for i, s in enumerate(segs)
            if i > 0 and s["role"] == "heading" and not PAGEREF.match(s["text"])]
    if not cuts:
        return [[0, len(segs), parent_title]]                  # no sub-headings

    bounds = sorted(set([1] + cuts + [len(segs)]))
    children = []
    for k in range(len(bounds) - 1):
        s, e = bounds[k], bounds[k + 1]
        is_head = segs[s]["role"] == "heading" and not PAGEREF.match(segs[s]["text"])
        title = segs[s]["text"] if is_head else f"{parent_title} — Introduction"
        est = sum(est_seg(segs[i]) for i in range(s, e))
        if children and est < min_sec:
            children[-1][1] = e                                # fold sliver backward
        else:
            children.append([s, e, title])

    # a sub-min leading intro has nothing before it — fold it forward into the
    # first real section instead of leaving a 2-second sliver track
    if len(children) >= 2:
        s0, e0, _ = children[0]
        if sum(est_seg(segs[i]) for i in range(s0, e0)) < min_sec:
            children[1][0] = s0
            children.pop(0)

    if len(children) < 2:
        return [[0, len(segs), parent_title]]                  # not worth splitting
    return [[0, 1, parent_title]] + children


def assemble_slice(seg_dir: Path, seg_slice):
    combined = AudioSegment.silent(duration=300)
    n = len(seg_slice)
    for j, seg in enumerate(seg_slice):
        f = seg_dir / seg["file"]
        if not f.exists() or f.stat().st_size == 0:
            continue
        try:
            clip = AudioSegment.from_file(f)
        except Exception as e:
            print(f"      !! skip undecodable {f.name}: {e}")
            continue
        combined += clip
        gap = C.SCENE_GAP_MS if (seg["role"] == "chapter_title" or j == n - 1) else M.pause_for(seg["role"])
        combined += AudioSegment.silent(duration=gap)
    return combined


CHILD_ID = re.compile(r"^\d+-\d+-")     # e.g. 073-04-... (a split child, not a parent)
FORCE = False     # set True by callers that must REGENERATE children (e.g. after a
                  # voice/text change). Default False keeps the initial split resumable.


def master_slice(seg_dir: Path, seg_slice, out_id: str) -> float:
    C.CHAPTERS.mkdir(parents=True, exist_ok=True)
    out_mp3 = C.CHAPTERS / f"{out_id}.mp3"
    # Resume optimization (initial split only): reuse an existing child mp3. MUST be
    # bypassed (FORCE) on any re-master, or children stay stale after a voice/text change.
    if not FORCE and CHILD_ID.match(out_id) and out_mp3.exists() and out_mp3.stat().st_size > 0:
        return M.duration_sec(out_mp3)
    combined = assemble_slice(seg_dir, seg_slice)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "raw.wav"
        combined.export(wav, format="wav")
        M.loudnorm(wav, out_mp3)
    return M.duration_sec(out_mp3)


def targets(chapters, only):
    """Level-1 tracks from Appendix 1 onward (appendices + back matter) whose
    mastered audio is longer than TARGET_MIN_SEC. The duration gate makes the
    script idempotent: an already-split parent is now title-only (~seconds), so a
    re-run skips it. Children (level 2) are never targets."""
    out = []
    for t in chapters:
        if only is not None:
            if t["order"] == only:
                out.append(t)
            continue
        if t["level"] != 1 or t["order"] < FIRST_ORDER:
            continue
        mp3 = C.CHAPTERS / f"{t['id']}.mp3"
        if mp3.exists() and M.duration_sec(mp3) > TARGET_MIN_SEC:
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print the plan, change nothing")
    ap.add_argument("--only", type=float, default=None, help="split only this order")
    args = ap.parse_args()

    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    tgts = targets(chapters, args.only)
    if not tgts:
        print("no tracks matched."); return
    print(f"splitting {len(tgts)} track(s): {[t['id'] for t in tgts]}\n")

    new_chapters, changed_ids = [], []
    tgt_ids = {t["id"] for t in tgts}

    for t in chapters:
        if t["id"] not in tgt_ids:
            new_chapters.append(t)
            continue
        plan = json.loads((C.SEGMENTS / t["id"] / "segments.json").read_text(encoding="utf-8"))
        segs = plan["segments"]                 # each: {file, role, text}
        track_est = sum(est_seg(s) for s in segs)
        floor = FLOOR_LONG if track_est > LONG_TRACK_SEC else FLOOR_SHORT
        parts = compute_parts(segs, t["title"], floor)
        if len(parts) == 1:
            print(f"  {t['id']}: no usable sub-headings — left as one track")
            new_chapters.append(t); continue

        seg_dir = C.SEGMENTS / t["id"]
        print(f"  {t['id']} -> {len(parts)} parts")
        for k, (s, e, title) in enumerate(parts):
            words = sum(len(segs[i]["text"].split()) for i in range(s, e))
            if k == 0:
                cid, order, level = t["id"], t["order"], 1
            else:
                cid = f"{int(t['order']):03d}-{k:02d}-{slugify(title)}"
                order, level = round(t["order"] + k / 100.0, 2), 2
            tag = "L1 parent" if k == 0 else f"L2 child {k}"
            if args.dry:
                print(f"      [{tag:11}] ~{words/150*60/60:4.1f}m  {cid:42} {title[:46]}")
                continue
            dur = master_slice(seg_dir, segs[s:e], cid)
            print(f"      [{tag:11}] {dur/60:4.1f}m  {cid:42} {title[:46]}")
            changed_ids.append(cid)
            new_chapters.append({
                "id": cid, "order": order, "level": level, "title": title,
                "segments": [{"role": segs[i]["role"], "text": segs[i]["text"]} for i in range(s, e)],
            })

    if args.dry:
        print("\n(dry run — nothing written)"); return

    # 1) chapters.json — source of truth now reflects the split
    C.CHAPTERS_JSON.write_text(json.dumps(new_chapters, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {C.CHAPTERS_JSON}  ({len(new_chapters)} tracks)")

    # 2) rebuild the served manifest from chapters.json + mastered mp3s
    import build_manifest
    build_manifest.main()

    # 3) stage manifest + changed/added mp3s to the web audio dir
    WEB_AUDIO.mkdir(parents=True, exist_ok=True)
    shutil.copy2(C.MANIFEST_JSON, WEB_AUDIO / "manifest.json")
    for cid in changed_ids:
        shutil.copy2(C.CHAPTERS / f"{cid}.mp3", WEB_AUDIO / f"{cid}.mp3")
    print(f"staged manifest + {len(changed_ids)} mp3(s) to {WEB_AUDIO}")
    print("\nNEXT: re-inline the manifest into index.html, then review.")


if __name__ == "__main__":
    main()
