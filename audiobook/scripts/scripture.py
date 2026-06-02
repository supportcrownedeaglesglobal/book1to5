"""
scripture.py — Expand abbreviated Bible references for spoken narration.

"Isa 6:1"  -> "Isaiah chapter 6 verse 1"
"1Co 13:4" -> "First Corinthians chapter 13 verse 4"
"Psa 19:12-14" -> "Psalm 19, verses 12 to 14"

Display text (chapters.json) is left untouched; this is applied only to the text
handed to edge-tts at render time, exactly like the pronunciation lexicon.
"""
import re

# letter-part of the abbreviation (lowercased, no leading number) -> spoken name
BOOKS = {
    "gen": "Genesis", "exo": "Exodus", "exod": "Exodus", "lev": "Leviticus",
    "num": "Numbers", "deu": "Deuteronomy", "deut": "Deuteronomy",
    "jos": "Joshua", "josh": "Joshua", "jdg": "Judges", "judg": "Judges",
    "rut": "Ruth", "ruth": "Ruth", "sa": "Samuel", "sam": "Samuel",
    "ki": "Kings", "kin": "Kings", "kgs": "Kings", "ch": "Chronicles",
    "chr": "Chronicles", "chro": "Chronicles", "chron": "Chronicles",
    "ezr": "Ezra", "ezra": "Ezra", "neh": "Nehemiah", "est": "Esther", "esth": "Esther",
    "job": "Job", "psa": "Psalm", "ps": "Psalm", "psalm": "Psalm", "psm": "Psalm",
    "pro": "Proverbs", "prov": "Proverbs", "ecc": "Ecclesiastes", "eccl": "Ecclesiastes",
    "son": "Song of Solomon", "sos": "Song of Solomon", "isa": "Isaiah",
    "jer": "Jeremiah", "lam": "Lamentations", "eze": "Ezekiel", "ezek": "Ezekiel",
    "dan": "Daniel", "hos": "Hosea", "joe": "Joel", "joel": "Joel",
    "amo": "Amos", "amos": "Amos", "oba": "Obadiah", "obad": "Obadiah",
    "jon": "Jonah", "jona": "Jonah", "mic": "Micah", "nah": "Nahum",
    "hab": "Habakkuk", "zep": "Zephaniah", "zeph": "Zephaniah", "hag": "Haggai",
    "zec": "Zechariah", "zech": "Zechariah", "mal": "Malachi",
    "mat": "Matthew", "matt": "Matthew", "mar": "Mark", "mark": "Mark",
    "luk": "Luke", "lk": "Luke", "luke": "Luke", "joh": "John", "john": "John", "jn": "John",
    "act": "Acts", "acts": "Acts", "rom": "Romans", "ro": "Romans",
    "co": "Corinthians", "cor": "Corinthians", "gal": "Galatians", "eph": "Ephesians",
    "phi": "Philippians", "php": "Philippians", "phil": "Philippians",
    "col": "Colossians", "th": "Thessalonians", "the": "Thessalonians", "thes": "Thessalonians",
    "ti": "Timothy", "tim": "Timothy", "tit": "Titus", "phm": "Philemon", "phlm": "Philemon",
    "heb": "Hebrews", "jam": "James", "jas": "James", "james": "James",
    "pe": "Peter", "pet": "Peter", "jud": "Jude", "jude": "Jude", "rev": "Revelation",
    # full names + spelled-out / variant forms found in the manuscript
    "genesis": "Genesis", "exodus": "Exodus", "leviticus": "Leviticus", "numbers": "Numbers",
    "deuteronomy": "Deuteronomy", "joshua": "Joshua", "judges": "Judges", "samuel": "Samuel",
    "kings": "Kings", "chronicles": "Chronicles", "nehemiah": "Nehemiah", "esther": "Esther",
    "psalms": "Psalm", "proverbs": "Proverbs", "ecclesiastes": "Ecclesiastes", "isaiah": "Isaiah",
    "jeremiah": "Jeremiah", "lamentations": "Lamentations", "ezekiel": "Ezekiel", "daniel": "Daniel",
    "hosea": "Hosea", "obadiah": "Obadiah", "jonah": "Jonah", "micah": "Micah", "nahum": "Nahum",
    "habakkuk": "Habakkuk", "zephaniah": "Zephaniah", "haggai": "Haggai", "zechariah": "Zechariah",
    "malachi": "Malachi", "matthew": "Matthew", "romans": "Romans", "roman": "Romans",
    "corinthians": "Corinthians", "galatians": "Galatians", "ephesians": "Ephesians",
    "philippians": "Philippians", "colossians": "Colossians", "thessalonians": "Thessalonians",
    "thess": "Thessalonians", "timothy": "Timothy", "titus": "Titus", "philemon": "Philemon",
    "hebrews": "Hebrews", "peter": "Peter", "revelation": "Revelation",
    "mathew": "Matthew", "proverb": "Proverbs",   # common misspelling / singular in source
}
ORD = {"1": "First", "2": "Second", "3": "Third"}

# optional leading number (1-3), book letters (2-5), opt period, space, chap:verse, opt -verse
_REF = re.compile(r"\b([1-3])?\s?([A-Za-z]{2,13})\.?\s+(\d{1,3}):(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?")


def _spoken(m):
    num, book, chap, v1, v2 = m.groups()
    key = book.lower()
    if key not in BOOKS:
        return m.group(0)                      # not a known book -> leave untouched
    name = BOOKS[key]
    if num:
        name = f"{ORD[num]} {name}"
    # Psalms are spoken "Psalm 19", not "Psalm chapter 19"
    head = f"{name} {chap}" if name == "Psalm" else f"{name} chapter {chap}"
    if v2:
        return f"{head}, verses {v1} to {v2}"
    return f"{head}, verse {v1}" if name == "Psalm" else f"{head} verse {v1}"


def expand(text: str) -> str:
    return _REF.sub(_spoken, text)
