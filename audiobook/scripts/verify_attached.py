import json, re
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5"); DATA = ROOT / "audiobook" / "data"
def dd(b):    return DATA if b == 5 else DATA / f"book-{b}"
def radir(b): return ROOT / "readalong" if b == 5 else ROOT / f"readalong/book-{b}"

allok = True
for b in (1, 2, 3, 4, 5):
    want = {d["image"] for d in json.loads((dd(b) / "diagrams.json").read_text(encoding="utf-8"))}
    attached = set()
    for jf in radir(b).glob("*.js"):
        t = jf.read_text(encoding="utf-8").strip()
        m = re.search(r"\]\s*=\s*(\{.*\})\s*;?\s*$", t, re.S)   # robust even if an id contains ']='
        if not m:
            continue
        try:
            o = json.loads(m.group(1))
        except Exception:
            continue
        for p in o.get("paragraphs", []):
            for im in (p.get("images") or []):
                attached.add(im)
    missing = sorted(want - attached)
    print(f"book {b}: diagrams.json={len(want)}  attached-in-readalong={len(want & attached)}  missing={len(missing)}")
    if missing:
        allok = False
        print("   MISSING:", ", ".join(Path(m).name for m in missing))
print("\nRESULT:", "ALL diagrams attached (every figure will display)" if allok else "SOME diagrams NOT attached — see above")
