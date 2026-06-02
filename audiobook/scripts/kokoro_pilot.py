"""
kokoro_pilot.py — Generate short Kokoro-82M samples for the 5-6 voice cast so the
owner can judge whether the (commercial-safe, Apache-2.0) voices clear the bar
before committing to a full re-render. Runs in the .venv-tts (Python 3.12 + torch).

Applies the SAME text transforms as production: pronunciation lexicon + scripture
expansion ("Isa 6:1" -> "Isaiah chapter 6 verse 1") + "US" -> "us".

Output: audiobook/out/_kokoro_pilot/<role>__<voice>.wav  (+ a combined cast clip)
"""
import re, sys
from pathlib import Path
import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config as C          # lightweight: only pathlib + dicts
import scripture            # lightweight: only re

# --- replicate render.py's lexicon pass (don't import render: it needs edge_tts) ---
_LEX = sorted(C.LEXICON.items(), key=lambda kv: -len(kv[0]))
def apply_lexicon(text):
    for word, say in _LEX:
        text = re.sub(rf"\b{re.escape(word)}\b", say, text)
        text = re.sub(rf"\b{re.escape(word.title())}\b", say, text)
    return text

def prep(text):
    return scripture.expand(apply_lexicon(text))

# --- cast mapping: current Azure voice -> best-available Kokoro voice ------------
# lang 'a' = American (af_/am_), 'b' = British (bf_/bm_). Males are Kokoro's weak
# spot (only af_heart/af_bella/bf_emma grade A/B), so this is exactly what we're testing.
CAST = [
    # role,        kokoro voice, lang, sample text
    ("narrator",   "bm_george",  "b", "The doctrine of the power of the age to come, narrated in full, that it may be heard as it was meant to be received."),
    ("father",     "am_onyx",    "a", "Behold, I have set before US life and death; therefore choose life, that both thou and thy seed may live, saith THE YAHWEH."),
    ("jesus",      "bm_daniel",  "b", "Isa 6:1 In the year that king Uzziah died I saw also the Lord sitting upon a throne, high and lifted up, and his train filled the temple."),
    ("shekinaih",  "bf_emma",    "b", "Spend time each day in the secret place, communing with US through repentance, prayer, and worship."),
    ("aaron",      "am_michael", "a", "LORD JESUS, teach me the secret of how to empty myself, that I may be wholly yielded unto THE ELOHIM."),
    # reference: Kokoro's single best (A-grade) voice, so the ceiling is audible
    ("ref_best_A", "af_heart",   "a", "This is Kokoro's highest-graded English voice, for comparison against the cast above."),
]

def main():
    from kokoro import KPipeline
    out = C.OUT / "_kokoro_pilot"
    out.mkdir(parents=True, exist_ok=True)
    pipes = {}
    combined = []
    SR = 24000
    for role, voice, lang, text in CAST:
        spoken = prep(text)
        print(f"[{role:10}] {voice:10} : {spoken[:70]}")
        pipe = pipes.get(lang) or pipes.setdefault(lang, KPipeline(lang_code=lang))
        chunks = [audio for _, _, audio in pipe(spoken, voice=voice, speed=1.0)]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        sf.write(out / f"{role}__{voice}.wav", audio, SR)
        combined.append(audio)
        combined.append(np.zeros(int(SR * 0.8), dtype=np.float32))   # 0.8s gap
    sf.write(out / "_cast_sample_all.wav", np.concatenate(combined), SR)
    print(f"\nwrote {len(CAST)} clips + _cast_sample_all.wav to {out}")

if __name__ == "__main__":
    main()
