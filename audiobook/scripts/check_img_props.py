from pathlib import Path
from PIL import Image

ROOT = Path(r"C:\Users\jda61\Documents\book5")
rows = []
for b in (1, 2, 3, 4, 5):
    for f in sorted((ROOT / f"images/book-{b}/diagrams").glob("*.jpg")):
        sz = f.stat().st_size
        with Image.open(f) as im:
            prog = bool(im.info.get("progressive") or im.info.get("progression"))
            dims = im.size
        rows.append((sz, dims, prog, str(f.relative_to(ROOT)).replace("\\", "/")))
rows.sort(reverse=True)
big = [r for r in rows if r[0] > 400_000]
prog = [r for r in rows if r[2]]
wide = [r for r in rows if r[1][0] > 1600 or r[1][1] > 1600]
tot = sum(r[0] for r in rows)
print(f"total images: {len(rows)}   total bytes: {tot//1024//1024} MB")
print(f">400KB: {len(big)}   progressive: {len(prog)}   any dim >1600px: {len(wide)}")
print("largest 15:")
for r in rows[:15]:
    print(f"  {r[0]//1024:>5}KB  {str(r[1]):>12}  prog={r[2]}  {r[3]}")
