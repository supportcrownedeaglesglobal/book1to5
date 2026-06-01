"""
master.py — Assemble synthesized segments into finished, Audible-grade chapter
MP3s: stitch segments with breathing pauses, normalize to EBU R128 / ACX loudness,
export 44.1kHz mono 128k MP3, and build data/manifest.json for the web player.

Usage:
  python master.py                 # master every rendered track
  python master.py --tracks 14     # master a single track (pilot)
"""
import argparse, json, subprocess, tempfile, os
from pathlib import Path
import static_ffmpeg
import static_ffmpeg.run as sfr
static_ffmpeg.add_paths()                      # put ffmpeg/ffprobe on PATH for pydub
from pydub import AudioSegment
import config as C

FFMPEG, FFPROBE = sfr.get_or_fetch_platform_executables_else_raise()
AudioSegment.converter = FFMPEG
AudioSegment.ffprobe   = FFPROBE

def pause_for(role):
    return C.PAUSE_AFTER.get(role, C.PARAGRAPH_GAP_MS)

def duration_sec(path):
    out = subprocess.run([FFPROBE, "-v", "quiet", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:    return round(float(out), 2)
    except: return 0.0

def assemble(track_dir: Path) -> AudioSegment:
    meta = json.loads((track_dir / "segments.json").read_text(encoding="utf-8"))
    combined = AudioSegment.silent(duration=300)
    for i, seg in enumerate(meta["segments"]):
        f = track_dir / seg["file"]
        if not f.exists() or f.stat().st_size == 0:
            continue
        try:
            clip = AudioSegment.from_file(f)
        except Exception as e:
            print(f"    !! skip undecodable {f.name}: {e}")
            continue
        combined += clip
        gap = C.SCENE_GAP_MS if (seg["role"] == "chapter_title" or i == len(meta["segments"]) - 1) \
              else pause_for(seg["role"])
        combined += AudioSegment.silent(duration=gap)
    return combined, meta

def loudnorm(in_wav: Path, out_mp3: Path):
    """Two-pass EBU R128 normalization: measure, then apply linearly so the
    true-peak ceiling (-3 dBTP, ACX-compliant) is actually respected."""
    import json as _json, re as _re
    base = f"I={C.LOUDNESS_I}:TP={C.LOUDNESS_TP}:LRA={C.LOUDNESS_LRA}"
    # pass 1 — measure
    p1 = subprocess.run([FFMPEG, "-hide_banner", "-i", str(in_wav),
                         "-af", f"highpass=f=70,loudnorm={base}:print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    m = _re.search(r"\{[^{}]+\}", p1.stderr.replace("\n", " "))
    d = _json.loads(m.group(0))
    # pass 2 — apply measured values, linear mode
    af = (f"highpass=f=70,loudnorm={base}:linear=true:"
          f"measured_I={d['input_i']}:measured_TP={d['input_tp']}:"
          f"measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:"
          f"offset={d['target_offset']},aresample={C.SAMPLE_RATE}")
    subprocess.run([FFMPEG, "-y", "-i", str(in_wav),
                    "-af", af, "-ac", str(C.CHANNELS),
                    "-ar", str(C.SAMPLE_RATE), "-b:a", C.BITRATE,
                    "-codec:a", "libmp3lame", str(out_mp3)],
                   check=True, capture_output=True)

def master_track(track_dir: Path):
    combined, meta = assemble(track_dir)
    C.CHAPTERS.mkdir(parents=True, exist_ok=True)
    out_mp3 = C.CHAPTERS / f"{meta['id']}.mp3"
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "raw.wav"
        combined.export(wav, format="wav")
        loudnorm(wav, out_mp3)
    dur = duration_sec(out_mp3)
    return {"id": meta["id"], "title": meta["title"], "level": meta["level"],
            "order": meta["order"], "durationSec": dur,
            "audioUrl": f"audio/book-5/{meta['id']}.mp3"}

def parse_range(spec, orders):
    if not spec: return set(orders)
    if "-" in spec:
        a, b = spec.split("-"); return set(range(int(a), int(b) + 1))
    return {int(spec)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", default="")
    args = ap.parse_args()

    rendered = sorted([d for d in C.SEGMENTS.iterdir() if (d / "segments.json").exists()])
    orders = {}
    for d in rendered:
        m = json.loads((d / "segments.json").read_text(encoding="utf-8"))
        orders[d] = m["order"]
    want = parse_range(args.tracks, orders.values())

    entries = []
    for d in rendered:
        if orders[d] not in want:
            continue
        e = master_track(d)
        entries.append(e)
        print(f"  [{e['order']:>3}] {e['id']:<46} {e['durationSec']/60:5.1f} min")

    # merge into manifest (preserve previously-mastered entries)
    manifest = {"title": C.BOOK_TITLE, "subtitle": C.BOOK_SUBTITLE, "chapters": []}
    if C.MANIFEST_JSON.exists():
        manifest = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in manifest["chapters"]}
    for e in entries:
        by_id[e["id"]] = e
    manifest["chapters"] = sorted(by_id.values(), key=lambda c: c["order"])
    manifest["totalSec"] = round(sum(c["durationSec"] for c in manifest["chapters"]), 1)
    C.MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"manifest: {len(manifest['chapters'])} chapters, "
          f"{manifest['totalSec']/3600:.2f}h total -> {C.MANIFEST_JSON}")

if __name__ == "__main__":
    main()
