"""
build_manifest.py — Build the FULL catalog manifest from chapters.json, merged
with whatever audio has actually been mastered. Every track in the book appears
in the interface immediately; rendered tracks are playable, the rest are listed
as "not yet recorded" with an estimated runtime.

Run after extract.py (and any time you master more tracks):
  python build_manifest.py
"""
import json, subprocess
import static_ffmpeg.run as sfr
import config as C

_, FFPROBE = sfr.get_or_fetch_platform_executables_else_raise()
WPM = 150.0

def duration_sec(path):
    out = subprocess.run([FFPROBE, "-v", "quiet", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:    return round(float(out), 2)
    except: return 0.0

def main():
    tracks = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    chapters = []
    ready_total = est_total = 0.0
    # Per-chapter cache-bust versions (edit data/versions.json; default 1). Appended to
    # the audio URL as ?v=<version> by the site so a bumped chapter beats the CDN cache.
    versions = json.loads((C.DATA / "versions.json").read_text(encoding="utf-8")) \
        if (C.DATA / "versions.json").exists() else {}
    for t in tracks:
        # skip the bare "Table of Contents" artifact — the interface IS the TOC
        if t["title"].strip().lower() == "table of contents":
            continue
        words = sum(len(s["text"].split()) for s in t["segments"])
        est = round(words / WPM * 60, 1)
        mp3 = C.CHAPTERS / f"{t['id']}.mp3"
        ready = mp3.exists() and mp3.stat().st_size > 0
        dur = duration_sec(mp3) if ready else 0.0
        est_total += est
        if ready:
            ready_total += dur
        chapters.append({
            "id": t["id"], "order": t["order"], "level": t["level"],
            "title": t["title"], "ready": ready,
            "durationSec": dur, "estSec": est,
            "audioUrl": f"{C.AUDIO_PREFIX}/{t['id']}.mp3" if ready else None,
            "version": versions.get(t["id"], 1),
        })
    manifest = {
        "title": C.BOOK_TITLE, "subtitle": C.BOOK_SUBTITLE,
        "chapters": chapters,
        "readyCount": sum(1 for c in chapters if c["ready"]),
        "totalCount": len(chapters),
        "totalSec": round(ready_total, 1),
        "estTotalSec": round(est_total, 1),
    }
    C.MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"catalog: {manifest['totalCount']} tracks, "
          f"{manifest['readyCount']} ready, "
          f"~{manifest['estTotalSec']/3600:.1f}h full / {manifest['totalSec']/3600:.2f}h recorded")
    print(f"wrote {C.MANIFEST_JSON}")

if __name__ == "__main__":
    main()
