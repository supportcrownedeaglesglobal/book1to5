"""
fix_scripture.py — Re-narrate Bible references in full form across the finished book.

It (1) re-synthesizes only the cached segments whose spoken text changes under
scripture.expand(), (2) re-masters only the finished tracks/children that contain
such a segment (standalone tracks from their own segment dir; split children from
their parent's cache), then (3) rebuilds the manifest, re-embeds it, and stages.

No track without a scripture reference is touched. Run after editing scripture.py:
  python fix_scripture.py            # do it
  python fix_scripture.py --dry      # report what would change, touch nothing
"""
import argparse, asyncio, json, shutil, sys
from pathlib import Path
import config as C
import render as R
import master as M
import scripture as SC
import split_appendices as SP

WEB = C.ROOT.parent / "audio" / "book-5"


def changed(text):
    return SC.expand(text) != text


async def rerender(dry):
    """Re-synthesize every cached segment whose spoken form changes."""
    affected = []
    for d in sorted(C.SEGMENTS.iterdir()):
        sj = d / "segments.json"
        if not sj.exists():
            continue
        for seg in json.loads(sj.read_text(encoding="utf-8"))["segments"]:
            if changed(seg["text"]):
                affected.append((d, seg))
    print(f"segments to re-narrate: {len(affected)}")
    if dry:
        for d, seg in affected[:6]:
            print(f"   {d.name}/{seg['file']}: {SC.expand(R.apply_lexicon(seg['text']))[:80]}")
        return
    tasks = []
    for d, seg in affected:
        out = d / seg["file"]
        if out.exists():
            out.unlink()
        spoken = SC.expand(R.apply_lexicon(seg["text"]))
        tasks.append(R.synth(spoken, R.role_to_voice(seg["role"]), out))
    await asyncio.gather(*tasks, return_exceptions=True)
    print(f"re-narrated {len(tasks)} segments (skipped {len(R.SKIPPED)})")


def remaster(dry):
    """Re-master only finished tracks/children containing a changed segment."""
    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    aff = {t["id"] for t in chapters if any(changed(s["text"]) for s in t["segments"])}
    print(f"finished tracks/children affected: {len(aff)}")
    if dry:
        for cid in list(aff)[:12]:
            print("   ", cid)
        return []

    done, i = [], 0
    while i < len(chapters):
        t = chapters[i]
        is_parent = t["level"] == 1 and i + 1 < len(chapters) and chapters[i + 1]["level"] == 2
        if is_parent:
            j = i + 1
            kids = []
            while j < len(chapters) and chapters[j]["level"] == 2:
                kids.append(chapters[j]); j += 1
            if any(k["id"] in aff for k in kids):
                seg_dir = C.SEGMENTS / t["id"]
                segs = json.loads((seg_dir / "segments.json").read_text(encoding="utf-8"))["segments"]
                floor = SP.FLOOR_LONG if sum(SP.est_seg(s) for s in segs) > SP.LONG_TRACK_SEC else SP.FLOOR_SHORT
                parts = SP.compute_parts(segs, t["title"], floor)
                if len(parts) - 1 != len(kids):
                    print(f"  !! {t['id']}: parts/kids mismatch ({len(parts)-1} vs {len(kids)}) — skipping"); i = j; continue
                for k in range(1, len(parts)):
                    child = kids[k - 1]                 # positional align -> use the stored id
                    if child["id"] in aff:
                        s, e, _ = parts[k]
                        dur = SP.master_slice(seg_dir, segs[s:e], child["id"])
                        done.append(child["id"]); print(f"  child {child['id']:46} {dur/60:5.1f}m")
            i = j; continue
        if t["id"] in aff and t["level"] == 1:          # standalone track
            seg_dir = C.SEGMENTS / t["id"]
            if (seg_dir / "segments.json").exists():
                M.master_track(seg_dir)
                done.append(t["id"]); print(f"  track {t['id']:46}")
        i += 1
    return done


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    await rerender(args.dry)
    done = remaster(args.dry)
    if args.dry:
        print("\n(dry run — nothing written)"); return

    import build_manifest, inline_manifest
    build_manifest.main()
    WEB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(C.MANIFEST_JSON, WEB / "manifest.json")
    for cid in done:
        shutil.copy2(C.CHAPTERS / f"{cid}.mp3", WEB / f"{cid}.mp3")
    inline_manifest.main()
    print(f"\ndone: re-narrated scripture, re-mastered {len(done)} tracks, manifest + index.html updated")


if __name__ == "__main__":
    asyncio.run(main())
