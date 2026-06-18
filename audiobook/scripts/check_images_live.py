import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
LIVE = "https://crownedeaglesglobal-beholdmymessengerseries-audio.com"

def head(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "v"}), timeout=30) as r:
            return r.status, int(r.headers.get("Content-Length", -1)), r.headers.get("Content-Type", "")
    except Exception as e:
        return None, -1, str(e)[:50]

bad = total = 0
for b in (1, 2, 3, 4, 5):
    for f in sorted((ROOT / f"images/book-{b}/diagrams").glob("*.jpg")):
        total += 1
        lsize = f.stat().st_size
        rel = f"images/book-{b}/diagrams/{f.name}"
        st, rsize, ctype = head(f"{LIVE}/{rel}")
        if st != 200 or rsize != lsize or "image" not in ctype:
            bad += 1
            print(f"   !! {rel}: http={st} live_size={rsize} local={lsize} type={ctype}")
print(f"checked {total} images on the live CDN; problems={bad}")
if not bad:
    print("   ALL images live (HTTP 200, image/*, size == local valid file)")
