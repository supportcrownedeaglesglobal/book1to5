"""apply_voice_fix.py — Re-master ONLY the tracks containing a re-voiced ROLE, after
render_kokoro.py --role has re-synthesized those segments with the new VOICE map.

Mirrors apply_name_fix.py exactly, but selects affected tracks by segment ROLE (e.g.
shekinaih, decree) instead of by text. Each affected track's clip slice is located by TEXT
in its own / parent cache (so split boundaries are never re-derived), then re-mastered with
split_appendices.master_slice (FORCE=True so cached children regenerate). A track whose slice
can't be located, or whose id isn't in the manifest, is reported UNMAPPED and left untouched.

  BMM_BOOK=5 python apply_voice_fix.py --roles shekinaih decree --check   # dry: report only
  BMM_BOOK=5 python apply_voice_fix.py --roles shekinaih decree           # re-master + refresh manifest
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import master as M
import split_appendices as SP

SP.FORCE = True                     # regenerate child mp3s even if a cached one exists


def has_role(segs, roles):
    return any(s.get("role") in roles for s in segs)


def find_slice(dir_segs, want_segs):
    """Contiguous slice of dir_segs (which carry 'file') whose stripped texts equal
    want_segs' stripped texts, or None — same matcher as apply_name_fix."""
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", nargs="+", required=True, help="segment roles that were re-voiced")
    ap.add_argument("--check", action="store_true", help="dry: report what WOULD re-master, master nothing")
    args = ap.parse_args()
    roles = set(args.roles)

    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in man["chapters"]}

    parent = None
    regen, unmapped = [], []
    for t in chapters:
        if t["level"] == 1:
            parent = t
        want = t.get("segments", [])
        if not has_role(want, roles):
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
        if args.check:
            regen.append(t["id"]); continue
        dur = SP.master_slice(seg_dir, sl, t["id"])
        by_id[t["id"]]["durationSec"] = dur
        regen.append(t["id"])
        if len(regen) % 20 == 0:
            print(f"    ... {len(regen)} re-mastered", flush=True)

    verb = "would re-master" if args.check else "re-mastered"
    print(f"BOOK {C.BOOK}: {verb} {len(regen)} tracks (roles={sorted(roles)}) | {len(unmapped)} UNMAPPED")
    if unmapped:
        print(f"  !! UNMAPPED (left untouched — investigate): {unmapped[:10]}")
    if not args.check:
        man["chapters"] = sorted(by_id.values(), key=lambda c: c["order"])
        man["totalSec"] = round(sum(c["durationSec"] for c in man["chapters"]), 1)
        C.MANIFEST_JSON.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  manifest refreshed: {len(man['chapters'])} chapters, {man['totalSec']/3600:.2f}h")


if __name__ == "__main__":
    main()
