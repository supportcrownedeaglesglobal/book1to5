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
    "decree":    ("am_fenrir", "a"),     # Heavenly Father — anointing & clear (was am_onyx, too deep)
    "shekinaih": ("af_heart", "a"),      # elegant, warm female (was bf_emma)
    "aaron":     ("am_michael", "a"),
}
DEFAULT = ("bm_george", "b")
SR = 24000

_LEX = sorted(C.LEXICON.items(), key=lambda kv: -len(kv[0]))
def apply_lexicon(t):
    for w, say in _LEX:
        t = re.sub(rf"\b{re.escape(w)}\b", say, t); t = re.sub(rf"\b{re.escape(w.title())}\b", say, t)
    return t

# ALL-CAPS in this manuscript is emphasis, not acronyms — but the TTS spells short caps
# letter-by-letter ("MY"->"M-Y", "SHE"->"S-H-E") and mis-stresses longer ones. Read every
# all-caps WORD in its normal lower-case form. Exceptions kept as-is: pure-consonant
# acronyms (KJV, TV, BC, MT, SG — spelled as letters) and Roman numerals (II, III, IV, VI).
_CAPS  = re.compile(r"\b[A-Z]{2,}\b")
_VOWEL = re.compile(r"[AEIOUY]")
_ROMAN = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
def normalize_caps(t):
    def repl(m):
        w = m.group(0)
        if not _VOWEL.search(w):        # KJV, TV, BC, DR, ST, MT, SG -> let the TTS spell it
            return w
        if _ROMAN.match(w):             # II, III, IV, VI -> keep (would mis-read as "ii")
            return w
        return w.lower()
    return _CAPS.sub(repl, t)

# The messenger is always read in FULL — his name becomes the canonical "J Aaron K David"
# everywhere it appears (title-case in the narrative, ALL-CAPS in emphatic passages). An optional
# leading "J"/"J." already present is consumed, so we never double-prefix; the full "Aaron K David"
# is required so the biblical "Moses and Aaron" and King "David" are never touched. Runs before
# normalize_caps, so an emphatic "J AARON K DAVID" still de-caps to "J aaron K david" (spoken
# "Jay Aaron Kay David"), matching the title-case form's pronunciation.
_JAARON = re.compile(r"\b(?:J\.?\s+)?(AARON|Aaron)\s+K\.?\s+(DAVID|David)\b")
def _jaaron(m):
    return "J AARON K DAVID" if m.group(1).isupper() else "J Aaron K David"
def prep(t):
    # lexicon first (special proper-noun respellings) → full messenger name → de-cap emphasis words
    t = _JAARON.sub(_jaaron, apply_lexicon(t))
    return scripture.expand(normalize_caps(t))
def speakable(t):
    return any(ch.isalnum() for ch in t)


def plan_segments():
    """Ensure out/segments/<id>/segments.json exists for every track in chapters.json,
    derived straight from the extract — so a Kokoro-only book needs no edge-tts render.py
    pass. Same per-segment filename scheme as render.py (<NNNN>-<role>.mp3); stores RAW
    text (lexicon/scripture are applied at synth time by prep())."""
    import json
    tracks = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    made = 0
    for t in tracks:
        tdir = C.SEGMENTS / t["id"]
        sj = tdir / "segments.json"
        if sj.exists():
            continue
        plan = [{"file": f"{i:04d}-{seg['role']}.mp3", "role": seg["role"], "text": seg["text"].strip()}
                for i, seg in enumerate(t["segments"]) if seg["text"].strip()]
        if not plan:
            continue
        tdir.mkdir(parents=True, exist_ok=True)
        sj.write_text(json.dumps({"id": t["id"], "title": t["title"], "level": t["level"],
                                  "order": t["order"], "segments": plan}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
        made += 1
    if made:
        print(f"planned {made} track(s) from chapters.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="render only this track dir id")
    ap.add_argument("--pattern", default=None,
                    help="re-render ONLY segments whose RAW text matches this regex, across all dirs, "
                         r"ignoring .kokoro_done — for targeted lexicon fixes (e.g. --pattern '\bMY\b'). "
                         "Re-applies the full text pipeline so a new lexicon entry takes effect.")
    ap.add_argument("--role", nargs="*", default=None,
                    help="re-render ONLY segments whose ROLE is in this set, across all dirs, ignoring "
                         ".kokoro_done — for a voice change (after editing the VOICE map for that role).")
    args = ap.parse_args()
    pat = re.compile(args.pattern) if args.pattern else None
    roles = set(args.role) if args.role else None
    targeted = pat is not None or roles is not None       # targeted modes ignore .kokoro_done
    if not targeted:
        plan_segments()                 # Kokoro-only: derive segment plans from chapters.json first

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
    total = 0
    for d in dirs:
        if not targeted and (d / ".kokoro_done").exists():
            continue                                  # whole-dir resume skip (full-render mode only)
        plan = json.loads((d / "segments.json").read_text(encoding="utf-8"))
        segs = plan["segments"]
        ok = 0
        for seg in segs:
            text = seg["text"].strip()
            out = d / seg["file"]
            if not speakable(text):
                continue
            if pat is not None and not pat.search(seg["text"]):
                continue                              # targeted mode: only segments matching the pattern
            if roles is not None and seg["role"] not in roles:
                continue                              # role mode: only segments of the requested role(s)
            voice, lang = VOICE.get(seg["role"], DEFAULT)
            spoken = prep(text)
            try:
                chunks = [a for _, _, a in pipe(lang)(spoken, voice=voice, speed=1.0)]
                audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
                sf.write(str(out), audio, SR, format="MP3")
                ok += 1
            except Exception as e:
                print(f"    !! {d.name}/{seg['file']}: {e}")
        if not targeted:
            (d / ".kokoro_done").write_text("ok", encoding="utf-8")
        if ok:
            total += ok
            print(f"  [{d.name:52}] {ok} segments", flush=True)
    print(f"done. {total} segments rendered.")


if __name__ == "__main__":
    main()
