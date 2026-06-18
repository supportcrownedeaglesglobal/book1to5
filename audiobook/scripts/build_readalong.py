"""
build_readalong.py — Emit per-track read-along data for the website's reading view.

For every PLAYABLE finished track it writes readalong/<id>.js (a one-line JSONP wrapper
that assigns the data into window.RA_CACHE — loadable via a <script> tag over file://, where
fetch() is blocked). The payload is:
  {"id","title","paragraphs":[{"role","text","start","end","image"?}, ...]}
start/end are seconds within that track's mastered MP3, derived from the SAME assembly
recipe as master.py (300ms lead-in + clip + role pause; SCENE_GAP around open/close) —
so the website can highlight the spoken paragraph without any forced alignment.

Split children are timed within their own MP3 (from the parent cache slice, same
boundaries split_appendices used). Title-only split parents (collapsible headers) get
no read-along file. Diagrams are attached from data/diagrams.json (see attach_images).

Run (3.14 env):  python build_readalong.py --check   # verify timing on one track
                 python build_readalong.py            # generate all
"""
import argparse, io, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import master as M
import split_appendices as SP

READALONG = C.READALONG
WEB_MANIFEST = C.WEB / "manifest.json"


def paragraphs(seg_dir: Path, seg_slice):
    """Replay master.concat_to_wav's timeline to get each paragraph's start/end (seconds).
    Uses the SAME silence-clip durations the master actually inserts (M.pause_sec), so the
    highlight matches the audio exactly with no accumulated drift."""
    out, t = [], M.pause_sec(300)                        # 300ms lead-in (matches master concat)
    n = len(seg_slice)
    for j, s in enumerate(seg_slice):
        f = seg_dir / s["file"]
        dur = M.duration_sec(f) if f.exists() else 0.0
        start = t
        t += dur
        out.append({"role": s["role"], "text": s["text"], "start": round(start, 2), "end": round(t, 2)})
        gap = C.SCENE_GAP_MS if (s["role"] == "chapter_title" or j == n - 1) else M.pause_for(s["role"])
        t += M.pause_sec(int(gap))
    return out


def split_parents(chapters):
    """level-1 tracks whose next track is a level-2 split sub-part (no own cache)."""
    sp = set()
    for i, t in enumerate(chapters):
        if t["level"] == 1 and i + 1 < len(chapters) and chapters[i + 1]["level"] == 2 \
           and not (C.SEGMENTS / chapters[i + 1]["id"] / "segments.json").exists():
            sp.add(t["id"])
    return sp


def load_diagrams():
    f = C.DATA / "diagrams.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _norm(x):
    """Collapse case + runs of non-alphanumerics to single spaces — tolerates the PDF's
    hyphenation / line-break artifacts in a diagram's after_text (e.g. 'ma- keth', 'YAH- WEH')
    that don't appear verbatim in the spoken segment text."""
    return re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).strip()


def attach_images(track_id, paras, diagrams):
    """Attach each diagram (matched by its after_text) to a paragraph's image list.
    Figures are processed in PAGE order; several may land on one paragraph (a run of testimony
    screenshots) and stack in that order. Falls back to a normalized (case/whitespace/punctuation
    -insensitive) substring match so PDF artifacts don't drop figures. A figure whose anchor matches
    an EARLIER paragraph than a previous (lower-page) figure is clamped forward, so figures can never
    display out of page order even when an anchor (e.g. a generic 'THE TRINITY') matches too early."""
    mine = sorted((d for d in diagrams if d.get("track") == track_id),
                  key=lambda d: int(d.get("page", 0)))
    last_idx = -1
    for d in mine:
        at = d.get("after_text") or ""
        if not at:
            continue
        idxs = [i for i, p in enumerate(paras) if at in p["text"]]           # exact substring
        if not idxs:                                                        # tolerate PDF artifacts
            nat = _norm(at)
            idxs = [i for i, p in enumerate(paras) if nat and nat in _norm(p["text"])]
        if not idxs:
            print(f"    !! diagram {d['image']}: no paragraph in {track_id} contains its after_text")
            continue
        idx = idxs[0]
        if idx < last_idx:                          # keep figures in page order (never invert)
            idx = last_idx
        paras[idx].setdefault("images", []).append(d["image"])
        last_idx = idx


def build_all():
    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    sp = split_parents(chapters)
    diagrams = load_diagrams()
    READALONG.mkdir(exist_ok=True)
    man = {c["id"]: c["durationSec"] for c in json.loads(WEB_MANIFEST.read_text(encoding="utf-8"))["chapters"]}
    # Split children carry no own segment-dir: each is a contiguous slice of its level-1
    # parent's cache. chapters.json stores each child's exact segment list, so we tile the
    # parent's segments by those STORED counts (a moving cursor) — the SAME boundaries
    # split_appendices mastered into each child's mp3. (Recomputing compute_parts here is
    # unsafe: if its floors/logic differ from when the book was split, the boundaries drift
    # and the read-along text desyncs from the audio — which is exactly what happened to
    # Appendix 8's children.)
    parent_dir, parent_segs, cursor = None, None, 0
    wrote, drift = 0, []
    for t in chapters:
        own = C.SEGMENTS / t["id"] / "segments.json"
        own_exists = own.exists()
        if t["level"] == 1:                              # new top-level track resets the slice cursor
            parent_dir = (C.SEGMENTS / t["id"]) if own_exists else None
            parent_segs = json.loads(own.read_text(encoding="utf-8"))["segments"] if own_exists else None
            cursor = 0
        if t["id"] in sp:                                # title-only split parent → no reader file,
            cursor += len(t.get("segments", []))         # but advance past the segment(s) it consumed
            continue
        if own_exists:                                   # standalone track: timed within its own cache
            segs = json.loads(own.read_text(encoding="utf-8"))["segments"]
            paras = paragraphs(C.SEGMENTS / t["id"], segs)
        elif parent_segs is not None:                    # split child: tile the parent cache by stored count
            n = len(t.get("segments", []))
            seg_slice = parent_segs[cursor:cursor + n]
            cursor += n
            paras = paragraphs(parent_dir, seg_slice)
        else:
            continue
        if not paras:
            continue
        attach_images(t["id"], paras, diagrams)
        payload = json.dumps({"id": t["id"], "title": t["title"], "paragraphs": paras}, ensure_ascii=False)
        # JSONP-style: a <script> tag assigns the data into RA_CACHE. Tag-loads of local files
        # work over file:// (where fetch() is blocked), so the reader works when index.html is
        # opened directly by double-clicking — not only over http. The site loads readalong/<id>.js
        # lazily via loadReadalong() in index.html.
        (READALONG / f"{t['id']}.js").write_text(
            f"(window.RA_CACHE=window.RA_CACHE||{{}})[{json.dumps(t['id'])}]={payload};\n",
            encoding="utf-8")
        wrote += 1
        if t["id"] in man:
            d = abs(paras[-1]["end"] - man[t["id"]])
            if d > 1.6:
                drift.append((t["id"], round(paras[-1]["end"], 1), man[t["id"]], round(d, 1)))
    print(f"wrote {wrote} read-along files to {READALONG}")
    if drift:
        print(f"  !! {len(drift)} tracks with >1.6s end-vs-duration drift:")
        for x in drift[:12]:
            print("    ", x)
    else:
        print("  timing check: all tracks within 1.6s of manifest duration  OK")


def check():
    man = {c["id"]: c["durationSec"] for c in json.loads(WEB_MANIFEST.read_text(encoding="utf-8"))["chapters"]}
    d = C.SEGMENTS / "014-chapter-1-1"
    segs = json.loads((d / "segments.json").read_text(encoding="utf-8"))["segments"]
    ps = paragraphs(d, segs)
    print(f"014-chapter-1-1: {len(ps)} paras, last end {ps[-1]['end']}s vs manifest {man['014-chapter-1-1']}s")
    assert abs(ps[-1]["end"] - man["014-chapter-1-1"]) < 1.6, "timing drift too high"
    print("monotonic:", all(ps[i]["start"] <= ps[i + 1]["start"] for i in range(len(ps) - 1)))
    print("OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify timing on one track, then exit")
    if ap.parse_args().check:
        check()
    else:
        build_all()
