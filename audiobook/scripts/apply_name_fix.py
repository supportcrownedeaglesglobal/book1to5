"""apply_name_fix.py — Re-master ONLY the tracks that name the messenger, after
render_kokoro.py --pattern has re-synthesized the affected segment clips with the new
"J Aaron K David" pronunciation.

Each final track in chapters.json (post-split) is one of:
  * a non-split track  — its own out/.../segments/<id>/ holds every clip;
  * a title-only split parent — its own segment-dir holds the full track, but only the
    leading title slice is its audio;
  * a split child — no segment-dir; its audio is a contiguous slice of the PARENT cache.

For every track whose text names the messenger we locate the matching clip slice by
TEXT (so we never depend on re-deriving split boundaries), then re-master just that slice
with split_appendices.master_slice (FORCE=True so cached children are regenerated). A track
whose slice can't be located, or whose id isn't in the manifest, is reported as UNMAPPED and
left untouched — a loud guard against silently corrupting audio.

  BMM_BOOK=2 python apply_name_fix.py --check    # dry: report what WOULD re-master, master nothing
  BMM_BOOK=2 python apply_name_fix.py            # re-master affected tracks + refresh manifest durations
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import master as M
import split_appendices as SP

SP.FORCE = True                     # regenerate child mp3s even if a cached one exists
NAME = re.compile(r"(AARON|Aaron)\s+K\.?\s+(DAVID|David)")
CHECK = "--check" in sys.argv


def has_name(segs):
    return any(NAME.search(s.get("text", "")) for s in segs)


def find_slice(dir_segs, want_segs):
    """Return the contiguous slice of dir_segs (which carry 'file') whose stripped texts
    equal want_segs' stripped texts, or None if it isn't found."""
    wt = [s["text"].strip() for s in want_segs]
    n = len(wt)
    if n == 0:
        return None
    dts = [s["text"].strip() for s in dir_segs]
    for i in range(len(dts) - n + 1):
        if dts[i:i + n] == wt:
            return dir_segs[i:i + n]
    return None


def main():
    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in man["chapters"]}

    parent = None
    regen, unmapped = [], []
    for t in chapters:
        if t["level"] == 1:
            parent = t
        want = t.get("segments", [])
        if not has_name(want):
            continue
        own = C.SEGMENTS / t["id"]
        if (own / "segments.json").exists():
            seg_dir = own                                   # non-split track / title-only parent
        elif parent is not None:
            seg_dir = C.SEGMENTS / parent["id"]             # split child → parent cache
        else:
            unmapped.append(t["id"]); continue
        dir_segs = json.loads((seg_dir / "segments.json").read_text(encoding="utf-8"))["segments"]
        sl = find_slice(dir_segs, want)
        if sl is None or t["id"] not in by_id:
            unmapped.append(t["id"]); continue
        if CHECK:
            regen.append(t["id"]); continue
        dur = SP.master_slice(seg_dir, sl, t["id"])
        by_id[t["id"]]["durationSec"] = dur
        regen.append(t["id"])
        if len(regen) % 20 == 0:
            print(f"    ... {len(regen)} re-mastered", flush=True)

    verb = "would re-master" if CHECK else "re-mastered"
    print(f"BOOK {C.BOOK}: {verb} {len(regen)} tracks | {len(unmapped)} UNMAPPED")
    if unmapped:
        print(f"  !! UNMAPPED (left untouched — investigate): {unmapped[:10]}")
    if not CHECK:
        man["chapters"] = sorted(by_id.values(), key=lambda c: c["order"])
        man["totalSec"] = round(sum(c["durationSec"] for c in man["chapters"]), 1)
        C.MANIFEST_JSON.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  manifest refreshed: {len(man['chapters'])} chapters, {man['totalSec']/3600:.2f}h")


if __name__ == "__main__":
    main()
