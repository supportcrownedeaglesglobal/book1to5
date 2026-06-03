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
import argparse, io, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import master as M
import split_appendices as SP

READALONG = C.ROOT.parent / "readalong"
WEB_MANIFEST = C.ROOT.parent / "audio" / "book-5" / "manifest.json"


def paragraphs(seg_dir: Path, seg_slice):
    """Replay master.assemble's timeline to get each paragraph's start/end (seconds)."""
    out, t = [], 0.300                                   # 300ms lead-in (master.assemble)
    n = len(seg_slice)
    for j, s in enumerate(seg_slice):
        f = seg_dir / s["file"]
        dur = M.duration_sec(f) if f.exists() else 0.0
        start = t
        t += dur
        out.append({"role": s["role"], "text": s["text"], "start": round(start, 2), "end": round(t, 2)})
        gap = C.SCENE_GAP_MS if (s["role"] == "chapter_title" or j == n - 1) else M.pause_for(s["role"])
        t += gap / 1000.0
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


def attach_images(track_id, paras, diagrams):
    """Attach each diagram (matched by its unique after_text) to a paragraph's image list.
    Several diagrams may land on one paragraph (e.g. a run of testimony screenshots) — they
    stack in diagrams.json order, which is book page order."""
    for d in diagrams:
        if d.get("track") != track_id:
            continue
        hits = [p for p in paras if d.get("after_text") and d["after_text"] in p["text"]]
        if hits:
            hits[0].setdefault("images", []).append(d["image"])
        else:
            print(f"    !! diagram {d['image']}: no paragraph in {track_id} contains its after_text")


def build_track(t, chapters, sp, parent_state, diagrams):
    """Return paragraphs for one final track, or None if it has no own/parent cache."""
    own = C.SEGMENTS / t["id"]
    if (own / "segments.json").exists():
        segs = json.loads((own / "segments.json").read_text(encoding="utf-8"))["segments"]
        return paragraphs(own, segs)
    # split child: slice of the parent cache, same boundaries as split_appendices
    parent = parent_state["parent"]
    pdir = C.SEGMENTS / parent["id"]
    segs = json.loads((pdir / "segments.json").read_text(encoding="utf-8"))["segments"]
    if parent_state["parts"] is None:
        floor = SP.FLOOR_LONG if sum(SP.est_seg(s) for s in segs) > SP.LONG_TRACK_SEC else SP.FLOOR_SHORT
        parent_state["parts"] = SP.compute_parts(segs, parent["title"], floor)
    s, e, _ = parent_state["parts"][parent_state["split_k"]]
    return paragraphs(pdir, segs[s:e])


def build_all():
    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    sp = split_parents(chapters)
    diagrams = load_diagrams()
    READALONG.mkdir(exist_ok=True)
    man = {c["id"]: c["durationSec"] for c in json.loads(WEB_MANIFEST.read_text(encoding="utf-8"))["chapters"]}
    state = {"parent": None, "parts": None, "split_k": 0}
    wrote, drift = 0, []
    for t in chapters:
        if t["level"] == 1:
            state.update(parent=t, parts=None, split_k=0)
        own_exists = (C.SEGMENTS / t["id"] / "segments.json").exists()
        if t["level"] == 2 and not own_exists:
            state["split_k"] += 1
        if t["id"] in sp:                                # title-only header → no reader file
            continue
        paras = build_track(t, chapters, sp, state, diagrams)
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
