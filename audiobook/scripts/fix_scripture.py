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
import argparse, asyncio, json, re, shutil, sys
from pathlib import Path
import config as C
import render as R
import master as M
import scripture as SC
import split_appendices as SP

WEB = C.ROOT.parent / "audio" / "book-5"


_PATTERN = None   # set by --pattern; when given, target raw text matching it instead


def changed(text):
    if _PATTERN is not None:
        return _PATTERN.search(text) is not None
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


_ALL = False   # set by --all: re-master every track (e.g. after a full voice swap)
_CHILDREN_ONLY = False  # set by --children-only: re-master only split children


def needs_remaster(text):
    """A track is re-mastered if --all is set, OR its scripture refs expand, OR
    (when a --pattern is given) it matches that pattern. Re-rendering is narrower —
    only the --pattern delta — because scripture segments were already re-rendered;
    but re-mastering must also cover scripture tracks (so a prior partial run is repaired)."""
    if _ALL:
        return True
    if SC.expand(text) != text:
        return True
    return _PATTERN is not None and _PATTERN.search(text) is not None


def remaster(dry):
    """Re-master only finished tracks/children containing a changed segment."""
    chapters = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    aff = {t["id"] for t in chapters if any(needs_remaster(s["text"]) for s in t["segments"])}
    print(f"finished tracks/children affected: {len(aff)}")
    if dry:
        for cid in list(aff)[:12]:
            print("   ", cid)
        return []

    # A track has its OWN segment cache iff it was rendered as a standalone track
    # (main-body chapters, original level-2 siblings, non-split back matter). A split
    # sub-part has no own dir — it is a slice of its parent's cache.
    # A split PARENT is a level-1 track whose next track is a level-2 split sub-part
    # (no own cache). Its own segment dir still holds the FULL original content, so it
    # must be re-mastered TITLE-ONLY (segment 0), never via master_track — which would
    # rebuild the full monolith and double-count with its children.
    split_parents = set()
    for i, t in enumerate(chapters):
        if t["level"] == 1 and i + 1 < len(chapters) and chapters[i + 1]["level"] == 2 \
           and not (C.SEGMENTS / chapters[i + 1]["id"] / "segments.json").exists():
            split_parents.add(t["id"])

    done, parent, parts, split_k = [], None, None, 0
    for t in chapters:
        if t["level"] == 1:
            parent, parts, split_k = t, None, 0
        own = C.SEGMENTS / t["id"]
        has_own = (own / "segments.json").exists()
        if t["level"] == 2 and not has_own:
            split_k += 1                                # position within parent's split children
        if _CHILDREN_ONLY:
            if not (t["level"] == 2 and not has_own):
                continue                                # only split children
        elif t["id"] not in aff:
            continue
        if t["id"] in split_parents:
            segs = json.loads((own / "segments.json").read_text(encoding="utf-8"))["segments"]
            SP.master_slice(own, segs[0:1], t["id"])    # title-only header, not the monolith
            done.append(t["id"]); print(f"  parent {t['id']:46} (title-only)")
        elif has_own:
            M.master_track(own)
            done.append(t["id"]); print(f"  track {t['id']:46}")
        else:
            pdir = C.SEGMENTS / parent["id"]
            segs = json.loads((pdir / "segments.json").read_text(encoding="utf-8"))["segments"]
            if parts is None:
                floor = SP.FLOOR_LONG if sum(SP.est_seg(s) for s in segs) > SP.LONG_TRACK_SEC else SP.FLOOR_SHORT
                parts = SP.compute_parts(segs, parent["title"], floor)
            s, e, _ = parts[split_k]                    # split_k indexes parts[1:]
            dur = SP.master_slice(pdir, segs[s:e], t["id"])
            done.append(t["id"]); print(f"  child {t['id']:46} {dur/60:5.1f}m")
    return done


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--pattern", default=None,
                    help="re-render segments whose RAW text matches this regex "
                         "(default: segments whose scripture refs expand). The full "
                         "render pipeline — lexicon + scripture — is always applied.")
    ap.add_argument("--remaster-only", action="store_true",
                    help="skip re-synthesis; only re-master affected tracks (segments already current)")
    ap.add_argument("--all", action="store_true",
                    help="re-master every track (use with --remaster-only after a full voice swap)")
    ap.add_argument("--children-only", action="store_true",
                    help="re-master ONLY split children (forces regen, bypassing the resume skip)")
    args = ap.parse_args()
    global _PATTERN, _ALL, _CHILDREN_ONLY
    if args.pattern:
        _PATTERN = re.compile(args.pattern)
    _ALL = args.all
    _CHILDREN_ONLY = args.children_only
    SP.FORCE = True            # any fix_scripture re-master must regenerate, not skip the resume cache

    if not args.remaster_only:
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
