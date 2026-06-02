"""
render_kokoro.py — Re-render EVERY segment with Kokoro-82M (Apache-2.0, commercial-
safe), replacing the edge-tts audio for the whole book. Runs in .venv-tts (torch+kokoro),
ideally on GPU. Overwrites out/segments/<track>/<NNNN>-<role>.mp3 in place, so the
existing master.py / split_appendices.py re-master step works unchanged afterward.

Applies the SAME text pipeline as production: pronunciation lexicon + scripture
expansion ("Isa 6:1" -> "Isaiah chapter 6 verse 1") + "US" -> "us".

Resumable: writes .kokoro_done in each track dir once all its segments are synthesized;
a re-run skips finished dirs. Idempotent.

  python render_kokoro.py                 # render all tracks
  python render_kokoro.py --only 073-appendix-8
"""
import argparse, re, sys
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config as C
import scripture

# cast: role -> (kokoro voice, lang_code)  — lang 'a'=American, 'b'=British.
# Mirrors render.py's role_to_voice, mapped to the voices auditioned in the pilot.
VOICE = {
    "chapter_title": ("bm_george", "b"), "heading": ("bm_george", "b"), "body": ("bm_george", "b"),
    "scripture": ("bm_daniel", "b"),     # Jesus
    "decree":    ("am_onyx",  "a"),      # Heavenly Father (deep)
    "shekinaih": ("bf_emma",  "b"),
    "aaron":     ("am_michael", "a"),
}
DEFAULT = ("bm_george", "b")
SR = 24000

_LEX = sorted(C.LEXICON.items(), key=lambda kv: -len(kv[0]))
def apply_lexicon(t):
    for w, say in _LEX:
        t = re.sub(rf"\b{re.escape(w)}\b", say, t); t = re.sub(rf"\b{re.escape(w.title())}\b", say, t)
    return t
def prep(t):
    return scripture.expand(apply_lexicon(t))
def speakable(t):
    return any(ch.isalnum() for ch in t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="render only this track dir id")
    args = ap.parse_args()

    from kokoro import KPipeline
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    pipes = {}
    def pipe(lang):
        if lang not in pipes:
            pipes[lang] = KPipeline(lang_code=lang, device=device)
        return pipes[lang]

    dirs = sorted(d for d in C.SEGMENTS.iterdir() if (d / "segments.json").exists())
    if args.only:
        dirs = [d for d in dirs if d.name == args.only]
    print(f"tracks to render: {len(dirs)}")

    import json
    for d in dirs:
        if (d / ".kokoro_done").exists():
            continue
        plan = json.loads((d / "segments.json").read_text(encoding="utf-8"))
        segs = plan["segments"]
        ok = 0
        for seg in segs:
            text = seg["text"].strip()
            out = d / seg["file"]
            if not speakable(text):
                continue
            voice, lang = VOICE.get(seg["role"], DEFAULT)
            spoken = prep(text)
            try:
                chunks = [a for _, _, a in pipe(lang)(spoken, voice=voice, speed=1.0)]
                audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
                sf.write(str(out), audio, SR, format="MP3")
                ok += 1
            except Exception as e:
                print(f"    !! {d.name}/{seg['file']}: {e}")
        (d / ".kokoro_done").write_text("ok", encoding="utf-8")
        print(f"  [{d.name:52}] {ok} segments", flush=True)
    print("done.")


if __name__ == "__main__":
    main()
