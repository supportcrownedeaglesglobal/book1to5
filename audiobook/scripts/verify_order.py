import json, re
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
def radir(b): return ROOT / "readalong" if b == 5 else ROOT / f"readalong/book-{b}"
def page_of(name):
    m = re.match(r"p(\d+)-", Path(name).name)
    return int(m.group(1)) if m else 0

total = 0
for b in (1, 2, 3, 4, 5):
    issues = []
    for jf in sorted(radir(b).glob("*.js")):
        t = jf.read_text(encoding="utf-8").strip()
        try:
            o = json.loads(t[t.index("]=") + 2:].rstrip().rstrip(";"))
        except Exception:
            continue
        seq = []                                    # (page, name) in reading order down the track
        for p in o.get("paragraphs", []):
            for im in (p.get("images") or []):
                seq.append((page_of(im), Path(im).name))
        for k in range(1, len(seq)):
            if seq[k][0] < seq[k - 1][0]:           # later-page figure displays before an earlier-page one
                issues.append(f"{o['id']}: {seq[k][1]} (p{seq[k][0]}) shows AFTER {seq[k-1][1]} (p{seq[k-1][0]})")
    print(f"book {b}: figure-order inversions = {len(issues)}")
    for x in issues[:20]:
        print("   !!", x)
    total += len(issues)
print("\nTOTAL inversions across all books:", total)
