import json, re, urllib.request
from pathlib import Path

LIVE = "https://crownedeaglesglobal-beholdmymessengerseries-audio.com"
def ra_url(b, cid): return f"{LIVE}/readalong/{cid}.js" if b == 5 else f"{LIVE}/readalong/book-{b}/{cid}.js"
def page_of(n):
    m = re.match(r"p(\d+)-", Path(n).name); return int(m.group(1)) if m else 0
def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "v"}), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)

fixed = [(1, "201-finalogue"), (4, "016-what-happens-when-a-man-dies"),
         (4, "165-1-africa"), (5, "016-chapter-1-2")]
allok = True
for b, cid in fixed:
    st, body = fetch(ra_url(b, cid))
    if st != 200:
        print(f"book {b}/{cid}: HTTP {st}"); allok = False; continue
    m = re.search(r"\]\s*=\s*(\{.*\})\s*;?\s*$", body, re.S)   # robust even if an id contains ']='
    if not m:
        print(f"book {b}/{cid}: parse error (no payload)"); allok = False; continue
    try:
        o = json.loads(m.group(1))
    except Exception as e:
        print(f"book {b}/{cid}: parse error {e}"); allok = False; continue
    seq = [(page_of(im), Path(im).name) for p in o["paragraphs"] for im in (p.get("images") or [])]
    inv = sum(1 for k in range(1, len(seq)) if seq[k][0] < seq[k - 1][0])
    print(f"book {b}/{cid}: live figures (display order) = {[s[1] for s in seq]}  inversions={inv}  {'OK' if inv == 0 else 'STILL BAD'}")
    if inv:
        allok = False
print("\nRESULT:", "live figure order CORRECT on all fixed tracks" if allok else "some tracks stale/wrong — recheck after deploy")
