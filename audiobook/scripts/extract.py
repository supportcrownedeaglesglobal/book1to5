"""
extract.py — Parse Book 5 .docx into an ordered list of tracks, each a list of
voiced segments. Output: data/chapters.json

Segmentation:
  * A new TRACK begins at every Heading 1 and Heading 2.
  * Within a track, each paragraph becomes a SEGMENT tagged with a speaker role,
    derived from structural cues (paragraph style + quotation + scripture refs),
    which are far more reliable than name-matching in this manuscript.

Speaker rules (override-able via data/overrides.json):
  chapter_title : Heading 1 / Heading 2                       -> narrator (announced)
  heading       : Heading 3-9, all-caps Normal sub-titles     -> narrator
  scripture     : Bible-reference header + following verses    -> jesus
  decree        : paragraph wholly wrapped in quotes (oracle)  -> father
  shekinaih     : "THROUGH SHEKINAIH" / Reflection Question     -> shekinaih
  aaron         : explicit AARON / K DAVID attribution          -> aaron
  body          : everything else (divine teaching prose)       -> narrator
"""
import json, re, sys
from docx import Document
import config as C

# --- text cleanup -----------------------------------------------------------
LIG = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
       "’": "'", "‘": "'", "“": '"', "”": '"',
       "–": "-", "—": "-", " ": " ", "﻿": "",
       "©": "(c)"}

def clean(t: str) -> str:
    for a, b in LIG.items():
        t = t.replace(a, b)
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t

# --- scripture detection ----------------------------------------------------
BOOKS = (r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
         r"Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm[s]?|Proverbs|"
         r"Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|"
         r"Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|"
         r"Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|"
         r"Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|"
         r"Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation")
SCRIPTURE_HEADER = re.compile(rf"^(?:[1-3]\s+)?(?:{BOOKS})\s+\d+(?::\d+)?", re.I)

def is_scripture_header(t):
    return bool(SCRIPTURE_HEADER.match(t)) and len(t.split()) <= 6

def wholly_quoted(t):
    return len(t) > 24 and t[0] in '"' and t[-1] in '"'

def role_for(style, text, in_scripture, prev_label):
    """Conservative, defensible attribution.
    Narrator carries the body. Distinct voices are used ONLY where a passage is
    genuinely direct speech / scripture / oracle decree — never because narration
    merely *mentions* a name."""
    up = text.upper()

    # An explicit reflection prompt is addressed to the listener -> Shekinaih (THE MAJOR).
    if prev_label == "reflection_label" and text.endswith("?"):
        return "shekinaih"

    # Direct attribution to Aaron / K David's own words.
    if re.search(r"\b(AARON|K DAVID)\b[^.]{0,40}\b(say|said|declar|speak|spoke|writes?|cried|prayed)\b",
                 text, re.I):
        return "aaron"

    if in_scripture:
        return "scripture"

    # Oracle pull-quote (a paragraph that is entirely a quotation).
    if wholly_quoted(text):
        # An oracle explicitly spoken THROUGH Shekinaih carries her voice; otherwise
        # it is THE FATHER / TRINITY decreeing.
        return "shekinaih" if "SHEKINAIH" in up else "decree"

    return "body"

def slugify(t):
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return t[:60] or "section"

def main():
    doc = Document(C.DOCX)
    tracks, cur = [], None
    order = 0
    in_scripture = False
    prev_label = None
    seen_slugs = {}

    for p in doc.paragraphs:
        raw = clean(p.text)
        if not raw:
            in_scripture = False
            continue
        style = p.style.name

        # skip the docx's own table-of-contents + picture placeholders (the site IS the TOC)
        if style.lower().startswith("toc") or style == "Pic":
            continue

        # --- new track on a part/chapter heading. Supports Heading 1/2 (Books 3/5) AND the
        #     custom manuscript styles in Books 1/2/4: "Part Heading Style" = part (L1),
        #     "Section Heading" = chapter (L2). ---
        if style in ("Heading 1", "Heading 2", "Part Heading Style", "Section Heading"):
            order += 1
            base = slugify(raw)
            n = seen_slugs.get(base, 0) + 1
            seen_slugs[base] = n
            slug = base if n == 1 else f"{base}-{n}"
            cur = {
                "id": f"{order:03d}-{slug}",
                "order": order,
                "level": 1 if style in ("Heading 1", "Part Heading Style") else 2,
                "title": raw,
                "segments": [],
            }
            tracks.append(cur)
            cur["segments"].append({"role": "chapter_title", "text": raw})
            in_scripture = False
            continue

        if cur is None:   # pre-title front matter -> seed a track
            order += 1
            cur = {"id": f"{order:03d}-front", "order": order, "level": 1,
                   "title": "Title Page", "segments": []}
            tracks.append(cur)

        # custom manuscript styles (Books 1/2/4) carry the speaker role directly:
        #   "God" = divine speech (decree/Father) · "Verse 1/Bold" = scripture (Jesus) ·
        #   sub-titles -> heading. Book 3/5 lack these styles, so this is a no-op there.
        _srole = {"God": "decree", "Verse 1": "scripture", "Verse Bold": "scripture",
                  "Section Sub Heading": "heading", "Chapter Caption": "heading"}.get(style)
        if _srole:
            cur["segments"].append({"role": _srole, "text": raw})
            in_scripture = False; prev_label = None
            continue

        # scripture run state machine
        if is_scripture_header(raw):
            in_scripture = True
            cur["segments"].append({"role": "scripture", "text": raw})
            continue
        if in_scripture and style != "List Paragraph":
            in_scripture = False

        if style.startswith("Heading"):
            cur["segments"].append({"role": "heading", "text": raw})
            in_scripture = False
            prev_label = None
            continue

        # remember a "Reflection Question" label so the following line gets her voice
        if raw.lower().rstrip(":").strip() in ("reflection question", "reflection questions", "reflection"):
            cur["segments"].append({"role": "heading", "text": raw})
            prev_label = "reflection_label"
            in_scripture = False
            continue

        role = role_for(style, raw, in_scripture, prev_label)
        cur["segments"].append({"role": role, "text": raw})
        prev_label = None

    # stats
    n_seg = sum(len(t["segments"]) for t in tracks)
    words = sum(len(s["text"].split()) for t in tracks for s in t["segments"])
    from collections import Counter
    roles = Counter(s["role"] for t in tracks for s in t["segments"])

    C.DATA.mkdir(parents=True, exist_ok=True)
    C.CHAPTERS_JSON.write_text(json.dumps(tracks, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"tracks={len(tracks)}  segments={n_seg}  words={words:,}  ~{words/150/60:.1f}h @150wpm")
    print("roles:", dict(roles))
    print(f"wrote {C.CHAPTERS_JSON}")

if __name__ == "__main__":
    main()
