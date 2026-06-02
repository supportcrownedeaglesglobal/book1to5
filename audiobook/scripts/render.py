"""
render.py — Synthesize every segment with its assigned voice via edge-tts.

Usage:
  python render.py                 # render ALL tracks (overnight job)
  python render.py --tracks 1-3    # render only tracks 1..3 (pilot)
  python render.py --tracks 12     # render a single track

Writes out/segments/<track-id>/<NNNN>-<role>.mp3 and skips files already done,
so the job is resumable.
"""
import argparse, asyncio, json, re, sys
import edge_tts
import config as C
import scripture

# --- pronunciation respelling ----------------------------------------------
_LEX = sorted(C.LEXICON.items(), key=lambda kv: -len(kv[0]))
def apply_lexicon(text: str) -> str:
    for word, say in _LEX:
        text = re.sub(rf"\b{re.escape(word)}\b", say, text)
        text = re.sub(rf"\b{re.escape(word.title())}\b", say, text)
    return text

def role_to_voice(role: str):
    mapping = {
        "chapter_title": "narrator", "heading": "narrator", "body": "narrator",
        "scripture": "jesus", "decree": "father",
        "shekinaih": "shekinaih", "aaron": "aaron",
    }
    return C.VOICES[mapping.get(role, "narrator")]

def parse_range(spec, n):
    if not spec:
        return range(1, n + 1)
    if "-" in spec:
        a, b = spec.split("-"); return range(int(a), int(b) + 1)
    return range(int(spec), int(spec) + 1)

SEM = asyncio.Semaphore(4)   # be polite to the edge endpoint
SKIPPED = []

def has_speakable(text: str) -> bool:
    return any(ch.isalnum() for ch in text)

async def synth(text, vcfg, out_path, attempts=5):
    """Resilient synth: skip unspeakable text, retry transient failures with
    backoff, and never raise — an overnight job must not die on one segment."""
    if not has_speakable(text):
        return                         # pure punctuation / empty -> nothing to say
    last = None
    for i in range(attempts):
        try:
            async with SEM:
                c = edge_tts.Communicate(text, vcfg["voice"], rate=vcfg["rate"], pitch=vcfg["pitch"])
                await c.save(str(out_path))
            if out_path.exists() and out_path.stat().st_size > 0:
                return
            raise RuntimeError("empty output")
        except Exception as e:
            last = e
            try:
                if out_path.exists(): out_path.unlink()
            except Exception: pass
            await asyncio.sleep(1.2 * (i + 1))   # backoff (outside the semaphore)
    SKIPPED.append(out_path.name)
    print(f"    !! skipped after {attempts} tries: {out_path.name} :: {last}")

async def render_track(track):
    tdir = C.SEGMENTS / track["id"]
    tdir.mkdir(parents=True, exist_ok=True)
    tasks, plan = [], []
    for i, seg in enumerate(track["segments"]):
        text = seg["text"].strip()
        if not text:
            continue
        vcfg = role_to_voice(seg["role"])
        # chapter title gets an explicit spoken announcement
        spoken = text
        if seg["role"] == "chapter_title":
            spoken = re.sub(r"\s+", " ", text)
        spoken = apply_lexicon(spoken)
        spoken = scripture.expand(spoken)      # "Isa 6:1" -> "Isaiah chapter 6 verse 1"
        out = tdir / f"{i:04d}-{seg['role']}.mp3"
        plan.append({"file": out.name, "role": seg["role"], "text": text})
        if out.exists() and out.stat().st_size > 0:
            continue
        tasks.append(synth(spoken, vcfg, out))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    (tdir / "segments.json").write_text(
        json.dumps({"id": track["id"], "title": track["title"],
                    "level": track["level"], "order": track["order"], "segments": plan},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return len(plan)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", default="")
    args = ap.parse_args()
    tracks = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    want = set(parse_range(args.tracks, len(tracks)))
    sel = [t for t in tracks if t["order"] in want]
    print(f"rendering {len(sel)} track(s): {[t['order'] for t in sel]}")
    for t in sel:
        n = await render_track(t)
        print(f"  [{t['order']:>3}] {t['id']:<48} segments={n}", flush=True)
    print(f"done. skipped {len(SKIPPED)} segment(s).")
    if SKIPPED:
        print("  re-run to retry skipped:", ", ".join(SKIPPED[:20]))

if __name__ == "__main__":
    asyncio.run(main())
