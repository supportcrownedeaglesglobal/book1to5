from pathlib import Path
from collections import Counter
from PIL import Image

ROOT = Path(r"C:\Users\jda61\Documents\book5")
modes = Counter()
nonrgb = []
for b in (1, 2, 3, 4, 5):
    for f in sorted((ROOT / f"images/book-{b}/diagrams").glob("*.jpg")):
        with Image.open(f) as im:
            m = im.mode
            modes[m] += 1
            if m not in ("RGB", "L"):                       # CMYK / YCCK / P etc. => browsers mis-render
                nonrgb.append((str(f.relative_to(ROOT)).replace("\\", "/"), m, im.size))
print("mode distribution:", dict(modes))
print(f"non-RGB images (browsers may garble these): {len(nonrgb)}")
for path, m, size in nonrgb:
    print(f"   {m:6} {size}  {path}")
