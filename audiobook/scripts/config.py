"""
Behold My Messenger audiobooks — shared configuration (multi-book).

Which book a pipeline run targets is set by the BMM_BOOK env var (1..5), default 5.
  BMM_BOOK=3 python extract.py        # operate on Book 3
Book 5 keeps its original flat paths (already produced + live); Books 1-4 nest under
data/book-N/, out/book-N/, audio/book-N/, images/book-N/, readalong/book-N/.

Voice cast, pronunciation lexicon, pauses and mastering targets are SHARED across all books.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------- which book
ROOT = Path(__file__).resolve().parents[1]                   # audiobook/
REPO = ROOT.parent                                           # repo root
SRC  = Path(r"C:\Users\jda61\OneDrive\Desktop\5books26Dec")  # source docx/pdf folder

BOOK = str(os.environ.get("BMM_BOOK", "5")).strip()          # "1".."5"

# Per-book source manuscript (docx = audio source) + metadata. PDFs are the bookmark/diagram
# reference (used by split_appendices / extract_diagrams), passed to those tools explicitly.
BOOKS = {
    "1": {"docx": SRC / "Book1Doc20251226_V2.docx",
          "title": "Behold My Messenger 1 — Behold My Glory", "subtitle": "The Victory"},
    "2": {"docx": SRC / "Book 2Doc20251226_V2.docx",
          "title": "Behold My Messenger 2 — Behold My Anointed", "subtitle": "Take up your cross and follow"},
    "3": {"docx": SRC / "Book 3 LATEST PRINT VERSION (2).docx",
          "title": "Behold My Messenger 3 — Behold My Names", "subtitle": "The Seven Names of the Trinity"},
    "4": {"docx": SRC / "Book4Doc20251226_V1.docx",
          "title": "Behold My Messenger 4 — Behold My Great White Throne", "subtitle": "Revelation · Judgement"},
    "5": {"docx": SRC / "Book_5_The_Resurrection_22_Dec_501m_7x10_Inch_Print_R1[2].docx",
          "title": "Behold My Messenger 5 — The Resurrection of the Dead",
          "subtitle": "The Doctrine of the Power of the Age to Come"},
}
_b = BOOKS[BOOK]
DOCX          = Path(_b["docx"])
BOOK_TITLE    = _b["title"]
BOOK_SUBTITLE = _b["subtitle"]

# ---------------------------------------------------------------- paths (per-book)
if BOOK == "5":                                              # original flat layout (live)
    DATA      = ROOT / "data"
    OUT       = ROOT / "out"
    READALONG = REPO / "readalong"
    WEB       = REPO / "audio" / "book-5"
    IMAGES    = REPO / "images" / "book-5"
    AUDIO_PREFIX = "audio/book-5"                            # manifest audioUrl prefix
else:                                                       # books 1-4 nest under book-N/
    DATA      = ROOT / "data" / f"book-{BOOK}"
    OUT       = ROOT / "out" / f"book-{BOOK}"
    READALONG = REPO / "readalong" / f"book-{BOOK}"
    WEB       = REPO / "audio" / f"book-{BOOK}"
    IMAGES    = REPO / "images" / f"book-{BOOK}"
    AUDIO_PREFIX = f"audio/book-{BOOK}"

SEGMENTS       = OUT / "segments"
CHAPTERS       = OUT / "chapters"
CHAPTERS_JSON  = DATA / "chapters.json"
MANIFEST_JSON  = DATA / "manifest.json"
OVERRIDES_JSON = DATA / "overrides.json"                    # optional manual speaker corrections
PLAYER_HTML    = REPO / f"book-{BOOK}.html"                 # the per-book player page

# ---------------------------------------------------------------- voice cast
# edge-tts neural voices (dev previews only — NOT shipped). Production audio is Kokoro
# (render_kokoro.py VOICE map). rate/pitch tuned per speaker.
VOICES = {
    "narrator":  {"voice": "en-GB-RyanNeural",                "rate": "-5%",  "pitch": "+0Hz",  "label": "Narrator"},
    "father":    {"voice": "en-US-BrianMultilingualNeural",   "rate": "-12%", "pitch": "-10Hz", "label": "Heavenly Father"},
    "jesus":     {"voice": "en-GB-ThomasNeural",              "rate": "-6%",  "pitch": "-2Hz",  "label": "Jesus"},
    "shekinaih": {"voice": "en-GB-SoniaNeural",               "rate": "-5%",  "pitch": "+0Hz",  "label": "Shekinaih"},
    "aaron":     {"voice": "en-US-AndrewMultilingualNeural",  "rate": "-5%",  "pitch": "+0Hz",  "label": "J Aaron K David"},
}

# Pauses (ms) inserted *after* a segment of the given role, for breathing room.
PAUSE_AFTER = {
    "chapter_title": 1100, "heading": 650, "scripture": 800, "decree": 900,
    "shekinaih": 600, "father": 700, "jesus": 650, "aaron": 500, "body": 420,
}
PARAGRAPH_GAP_MS = 380          # default gap between ordinary paragraphs
SCENE_GAP_MS     = 1400         # gap around chapter open/close

# ---------------------------------------------------------------- mastering (ACX / Audible spec)
LOUDNESS_I   = -19.0
LOUDNESS_TP  = -3.0
LOUDNESS_LRA = 11.0
SAMPLE_RATE  = 44100
BITRATE      = "128k"           # MP3 CBR; Audible-grade for spoken word
CHANNELS     = 1                # mono spoken word

# ---------------------------------------------------------------- pronunciation (shared)
# Proper nouns / acronyms the TTS mispronounces. Plain-text respelling before synthesis.
# Short ALL-CAPS pronouns get spelled out letter-by-letter ("MY"->"M-Y") — respell to the word.
LEXICON = {
    "SHEKINAIH": "Shekinaya",
    "ELOHIM":    "El-oh-heem",
    "ADONAI":    "Ah-doh-nye",
    "YESHUA":    "Yeh-shoo-ah",
    "YAHWEH":    "Yah-weh",
    "CEG":       "Crowned Eagles Global",
    "US":        "us",     # divine pronoun "US" -> spoken "us", not the letters "U-S"
    "MY":        "my",     # divine pronoun "MY" -> spoken "my", not the letters "M-Y" (e.g. "BEHOLD MY MESSENGER")
}
