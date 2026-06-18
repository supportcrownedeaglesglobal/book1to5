from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
try:
    from PIL import Image
    havePIL = True
except Exception:
    havePIL = False
print("PIL available:", havePIL)

issues, total = [], 0
for b in (1, 2, 3, 4, 5):
    for f in sorted((ROOT / f"images/book-{b}/diagrams").glob("*.jpg")):
        total += 1
        data = f.read_bytes()
        size = len(data)
        magic_ok = size >= 3 and data[:3] == b"\xff\xd8\xff"
        dec_ok, info = None, None
        if havePIL:
            try:
                im = Image.open(f); im.load()
                info = f"{im.size} {im.mode}"
                dec_ok = im.size[0] > 0 and im.size[1] > 0
            except Exception as e:
                dec_ok, info = False, f"{type(e).__name__}: {e}"[:60]
        if size < 200 or not magic_ok or (havePIL and not dec_ok):
            issues.append((str(f.relative_to(ROOT)).replace("\\", "/"), size, magic_ok, dec_ok, info))

print(f"checked {total} diagram images; PROBLEM images = {len(issues)}")
for path, size, magic, dec, info in issues:
    print(f"   !! {path}  size={size}  jpeg_magic={magic}  decodable={dec}  {info}")
if not issues:
    print("   all images are valid, decodable JPEGs")
