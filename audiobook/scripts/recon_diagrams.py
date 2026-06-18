import json
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
DATA = ROOT / "audiobook" / "data"

try:
    import fitz
    fitzv = getattr(fitz, "__version__", "?")
except Exception as e:
    fitzv = f"NOT AVAILABLE: {type(e).__name__}: {e}"
print("PyMuPDF (fitz):", fitzv)

def datadir(b): return DATA if b == 5 else DATA / f"book-{b}"
def imgdir(b):  return ROOT / f"images/book-{b}/diagrams"

print("\n--- orphan scan ---")
for b in (1, 2, 3, 4, 5):
    dj = json.loads((datadir(b) / "diagrams.json").read_text(encoding="utf-8"))
    ref = {Path(d["image"]).name for d in dj}
    files = sorted(p.name for p in imgdir(b).glob("*.jpg"))
    orph = [f for f in files if f not in ref]
    print(f"book {b}: files={len(files)} referenced={len(ref)} orphans={len(orph)}")
    if orph:
        print("   ", ", ".join(orph))

print("\n--- PDF search ---")
bases = [Path(r"C:\Users\jda61\OneDrive\Desktop\5books26Dec"),
         Path(r"C:\Users\jda61\OneDrive\Desktop"), ROOT, ROOT / "audiobook"]
seen = set()
for base in bases:
    if base.exists():
        try:
            for pdf in base.rglob("*.pdf"):
                if pdf not in seen:
                    seen.add(pdf)
                    print("  ", pdf, f"({pdf.stat().st_size//1024} KB)")
        except Exception as e:
            print(f"   (scan error in {base}: {e})")
if not seen:
    print("   no PDFs found in searched locations")
