import json, urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5"); DATA = ROOT / "audiobook" / "data"
LIVE = "https://crownedeaglesglobal-beholdmymessengerseries-audio.com"
def dd(b):     return DATA if b == 5 else DATA / f"book-{b}"
def ra_url(b, cid): return f"{LIVE}/readalong/{cid}.js" if b == 5 else f"{LIVE}/readalong/book-{b}/{cid}.js"

def fetch(url, head=False, t=30):
    try:
        req = urllib.request.Request(url, method="HEAD" if head else "GET", headers={"User-Agent": "v"})
        with urllib.request.urlopen(req, timeout=t) as r:
            return r.status, (b"" if head else r.read().decode("utf-8", "replace"))
    except Exception as e:
        return None, str(e)

for b in (1, 2, 3):
    dj = json.loads((dd(b) / "diagrams.json").read_text(encoding="utf-8"))
    orph = [d for d in dj if int(d.get("page", 0)) >= 268]          # the newly-added back-matter figures
    imgok = sum(1 for d in orph if fetch(f"{LIVE}/{d['image']}", head=True)[0] == 200)
    print(f"\nBOOK {b}: new figures={len(orph)}  images live (HTTP 200)={imgok}/{len(orph)}")
    # live read-along reflects new attachments?
    seen, checked, raok = set(), 0, 0
    for d in orph:
        if d["track"] in seen:
            continue
        seen.add(d["track"]); checked += 1
        if checked > 6:
            break
        st, body = fetch(ra_url(b, d["track"]))
        nm = Path(d["image"]).name
        present = (st == 200 and nm in body)
        raok += present
        print(f"   live readalong {d['track'][:46]:<46} {nm}: {'OK' if present else f'present={nm in (body or chr(34)+chr(34))} http={st}'}")
    print(f"   -> {raok}/{checked} sampled tracks already serve their new figure live")
