"""List diagrams whose after_text matches MORE THAN ONE paragraph in their track (ambiguous anchor
-> the reader may attach the figure to the wrong occurrence)."""
import json, re
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5"); DATA = ROOT / "audiobook" / "data"
def _dehyph(t):
    t = t or ""
    t = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", t)
    t = re.sub(r"(\d)-\s+(\d)", r"\1-\2", t)
    return t
def dd(b):    return DATA if b == 5 else DATA / f"book-{b}"
def radir(b): return ROOT / "readalong" if b == 5 else ROOT / f"readalong/book-{b}"

def load_ra(b):
    paras = {}
    for jf in radir(b).glob("*.js"):
        t = jf.read_text(encoding="utf-8").strip()
        try:
            o = json.loads(t[t.index("]=") + 2:].rstrip().rstrip(";"))
        except Exception:
            continue
        paras[o["id"]] = [p["text"] for p in o.get("paragraphs", [])]
    return paras

total = 0
for b in (1, 2, 3, 4, 5):
    dj = json.loads((dd(b) / "diagrams.json").read_text(encoding="utf-8"))
    paras = load_ra(b)
    amb = []
    for d in dj:
        trk, at = d["track"], _dehyph(d.get("after_text") or "")
        ps = paras.get(trk)
        if not ps or not at:
            continue
        hits = [i for i, p in enumerate(ps) if at in p]
        if len(hits) > 1:
            amb.append((Path(d["image"]).name, trk, hits))
    print(f"book {b}: {len(amb)} figures with ambiguous after_text")
    for nm, trk, hits in amb:
        print(f"    {nm}  {trk}  matches paras {hits}")
    total += len(amb)
print(f"\nTOTAL ambiguous-anchor figures: {total}")
