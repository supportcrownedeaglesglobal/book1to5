"""
Book 5 Audiobook — shared configuration.
Voice cast, paths, pronunciation lexicon, audio mastering targets.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT      = Path(__file__).resolve().parents[1]          # audiobook/
DOCX      = Path(r"C:\Users\jda61\OneDrive\Desktop\5books26Dec\Book_5_The_Resurrection_22_Dec_501m_7x10_Inch_Print_R1[2].docx")
DATA      = ROOT / "data"
OUT       = ROOT / "out"
SEGMENTS  = OUT / "segments"
CHAPTERS  = OUT / "chapters"
CHAPTERS_JSON = DATA / "chapters.json"
MANIFEST_JSON = DATA / "manifest.json"
OVERRIDES_JSON = DATA / "overrides.json"   # optional manual speaker corrections

# ---------------------------------------------------------------- voice cast
# edge-tts neural voices. rate/pitch tuned per speaker for an Audible-grade cast.
VOICES = {
    "narrator":  {"voice": "en-GB-RyanNeural",                "rate": "-5%",  "pitch": "+0Hz",  "label": "Narrator"},
    "father":    {"voice": "en-US-BrianMultilingualNeural",   "rate": "-12%", "pitch": "-10Hz", "label": "Heavenly Father"},
    "jesus":     {"voice": "en-GB-ThomasNeural",              "rate": "-6%",  "pitch": "-2Hz",  "label": "Jesus"},
    "shekinaih": {"voice": "en-GB-SoniaNeural",               "rate": "-5%",  "pitch": "+0Hz",  "label": "Shekinaih"},
    "aaron":     {"voice": "en-US-AndrewMultilingualNeural",  "rate": "-5%",  "pitch": "+0Hz",  "label": "J Aaron K David"},
}

# Pauses (ms) inserted *after* a segment of the given role, for breathing room.
PAUSE_AFTER = {
    "chapter_title": 1100,
    "heading":       650,
    "scripture":     800,
    "decree":        900,
    "shekinaih":     600,
    "father":        700,
    "jesus":         650,
    "aaron":         500,
    "body":          420,
}
PARAGRAPH_GAP_MS = 380          # default gap between ordinary paragraphs
SCENE_GAP_MS     = 1400         # gap around chapter open/close

# ---------------------------------------------------------------- mastering (ACX / Audible spec)
# ACX: RMS -23 to -18 dB, peak <= -3 dBTP, noise floor <= -60 dB.
# We target EBU R128 integrated loudness -19 LUFS (centre of ACX RMS band for speech),
# true-peak -3 dBTP. ffmpeg loudnorm handles this.
LOUDNESS_I   = -19.0
LOUDNESS_TP  = -3.0
LOUDNESS_LRA = 11.0
SAMPLE_RATE  = 44100
BITRATE      = "128k"           # MP3 CBR; Audible-grade for spoken word
CHANNELS     = 1                # mono spoken word

# ---------------------------------------------------------------- pronunciation
# Proper nouns / acronyms edge-tts mispronounces. Applied as plain-text respelling
# before synthesis (kept conservative — only fix the clear failures).
LEXICON = {
    "SHEKINAIH": "Shekinaya",
    "ELOHIM":    "El-oh-heem",
    "ADONAI":    "Ah-doh-nye",
    "YESHUA":    "Yeh-shoo-ah",
    "YAHWEH":    "Yah-weh",
    "CEG":       "Crowned Eagles Global",
    "US":        "us",     # divine pronoun "US" -> spoken "us", not the letters "U-S"
}

BOOK_TITLE   = "Behold My Messenger 5 — The Resurrection of the Dead"
BOOK_SUBTITLE = "The Doctrine of the Power of the Age to Come"
