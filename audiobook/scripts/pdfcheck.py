import fitz, json
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5"); DATA = ROOT / "audiobook" / "data"
DESK = Path(r"C:\Users\jda61\OneDrive\Desktop\5books26Dec")
DESK2 = Path(r"C:\Users\jda61\OneDrive\Desktop")
cands = {
    1: ["Book1Doc20251226.pdf"],
    2: ["Book 2Doc20251226.pdf"],
    3: ["Book 3 Interactive.pdf", "Book 3 LATEST PRINT VERSION.pdf"],
}
def dd(b): return DATA if b == 5 else DATA / f"book-{b}"

for b, names in cands.items():
    dj = json.loads((dd(b) / "diagrams.json").read_text(encoding="utf-8"))
    refpages = sorted({d["page"] for d in dj})
    imgnums = sorted(int(p.name[1:4]) for p in (ROOT / f"images/book-{b}/diagrams").glob("*.jpg"))
    orphpages = sorted(set(p for p in imgnums if p not in refpages))
    print(f"\n=== BOOK {b}: ref pages {refpages[:4]}..{refpages[-2:]}  orphan pages {orphpages[:4]}..{orphpages[-2:]}  max={max(imgnums)} ===")
    for nm in names:
        pdf = DESK / nm
        if not pdf.exists():
            pdf = DESK2 / nm
        if not pdf.exists():
            print(f"   MISSING: {nm}"); continue
        doc = fitz.open(str(pdf)); pc = doc.page_count
        rhit = sum(1 for pg in refpages if pg <= pc and doc.get_page_images(pg - 1))
        ohit = sum(1 for pg in orphpages if pg <= pc and doc.get_page_images(pg - 1))
        print(f"   {nm}: pages={pc}  ref-pages-with-image={rhit}/{len(refpages)}  orphan-pages-with-image={ohit}/{len(orphpages)}")
        doc.close()
