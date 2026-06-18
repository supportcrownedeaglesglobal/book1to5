"""Backfill an "occ" (1-based occurrence index) onto diagrams whose after_text matches more than
one paragraph in their track, so the reader attaches them to the occurrence place_diagrams MEANT
(by the figure's PDF page -> paragraph), not just the first match. Only ambiguous entries change.

  BMM_BOOK=3 python fix_ambiguous_occ.py "<book-3 pdf>"
"""
import sys, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import config as C
import place_diagrams as PD
import fitz

PDF = sys.argv[1]

def _dehyph(t):
    t = t or ""
    t = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", t)
    t = re.sub(r"(\d)-\s+(\d)", r"\1-\2", t)
    return t

DJ = C.DATA / "diagrams.json"
dj = json.loads(DJ.read_text(encoding="utf-8"))
paras = PD.load_paras()                                    # {track_id: [para dicts]} from readalong
doc = fitz.open(PDF)
tracks = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
page_track = PD.page_track_map(doc, tracks, paras)
span = {}
for pg, tid in page_track.items():
    s, e = span.get(tid, (pg, pg)); span[tid] = (min(s, pg), max(e, pg))
anchors = {name: (page, anchor) for name, page, anchor in PD.image_anchors(doc)}

changed = cleared = 0
for d in dj:
    tid, at = d.get("track"), _dehyph(d.get("after_text") or "")
    plist = paras.get(tid)
    if not plist or not at:
        if d.pop("occ", None) is not None: cleared += 1
        continue
    matches = [j for j, p in enumerate(plist) if at in p["text"]]
    if len(matches) <= 1:                                   # unambiguous now -> no occ needed
        if d.pop("occ", None) is not None: cleared += 1
        continue
    pa = anchors.get(Path(d["image"]).name)
    if not pa:
        continue
    page, anchor = pa
    atoks = PD.toks(anchor)
    best_i, best = -1, 0
    for pi, p in enumerate(plist):                          # place_diagrams' content match
        inter = len(atoks & PD.toks(p["text"]))
        if inter > best:
            best, best_i = inter, pi
    if best >= 2:
        target = best_i
    else:                                                   # else its fractional page position in the track
        sp, ep = span.get(tid, (page, page))
        frac = min(1.0, max(0.0, (page - sp) / max(1, ep - sp)))
        target = round(frac * (len(plist) - 1))
    occ = matches.index(min(matches, key=lambda j: abs(j - target))) + 1
    print(f"   {Path(d['image']).name} {tid}: matches {matches}, target~{target} -> occ {occ}")
    if d.get("occ") != occ:
        d["occ"] = occ; changed += 1

DJ.write_text(json.dumps(dj, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"book {C.BOOK}: set/updated occ on {changed} ambiguous figures (cleared {cleared} stale)")
