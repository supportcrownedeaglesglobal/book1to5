"""Build functions/api/_chapters.json (compact grounding map) from all books' chapters.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT  = HERE.parent.parent / "functions" / "api" / "_chapters.json"
EXCERPT_WORDS = 150

def _excerpt(track):
    txt = " ".join(s["text"] for s in track.get("segments", []) if s.get("role") != "chapter_title")
    return " ".join(txt.split()[:EXCERPT_WORDS])

def build_map(books):  # books: {book_num: [tracks]}
    m = {}
    for n, tracks in books.items():
        for t in tracks:
            if not t.get("segments"): continue
            m[t["id"]] = {"book": n, "title": t["title"],
                          "url": f"book-{n}.html#{t['id']}", "excerpt": _excerpt(t)}
    return m

def _load(n):
    p = DATA / ("chapters.json" if n == 5 else f"book-{n}/chapters.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

def main():
    books = {n: _load(n) for n in (1, 2, 3, 4, 5)}
    m = build_map(books)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}  ({len(m)} tracks)")

if __name__ == "__main__":
    main()
