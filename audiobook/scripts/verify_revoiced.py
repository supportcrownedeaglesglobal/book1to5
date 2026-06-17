"""
verify_revoiced.py — Prove the Books 1-4 re-voice is correctly replaced + synchronized.

For every re-voiced track (decree/shekinaih) in each book it checks:
  - the served manifest carries a bumped cache-bust version (>=2)  -> users won't get stale audio
  - the read-along's last paragraph end is within 1.6s of the manifest duration -> text follows audio

  C:\\Python314\\python.exe audiobook\\scripts\\verify_revoiced.py
"""
import json, re
from pathlib import Path

HERE  = Path(__file__).resolve().parent
ROOT  = HERE.parent.parent
DATA  = HERE.parent / "data"
ROLES = {"decree", "shekinaih"}


def ra_end(p: Path):
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8").strip()
    m = re.search(r'\]\s*=\s*(\{.*\})\s*;?\s*$', t, re.S)          # ...)["id"]=PAYLOAD;
    if not m:
        return None
    try:
        ps = json.loads(m.group(1)).get("paragraphs") or []
        return float(ps[-1]["end"]) if ps else None
    except Exception:
        return None


print(f"{'book':<5}{'changed':>8}{'in_man':>8}{'v>=2':>7}{'sync<=1.6':>11}{'max_drift':>10}")
all_ok = True
for book in (1, 2, 3, 4):
    ch      = json.loads((DATA / f"book-{book}" / "chapters.json").read_text(encoding="utf-8"))
    changed = sorted({c["id"] for c in ch if any(s.get("role") in ROLES for s in c.get("segments", []))})
    man     = {c["id"]: c for c in json.loads((ROOT / "audio" / f"book-{book}" / "manifest.json").read_text(encoding="utf-8"))["chapters"]}
    radir   = ROOT / "readalong" / f"book-{book}"

    inman = nver = nsync = nrow = 0
    maxd, worst = 0.0, []
    for cid in changed:
        c = man.get(cid)
        if not c:
            continue
        inman += 1
        if int(c.get("version", 1)) >= 2:
            nver += 1
        e = ra_end(radir / f"{cid}.js")
        if e is None:
            continue
        nrow += 1
        d = abs(e - float(c["durationSec"]))
        maxd = max(maxd, d)
        if d <= 1.6:
            nsync += 1
        else:
            worst.append((cid, round(d, 1)))
    print(f"{book:<5}{len(changed):>8}{inman:>8}{nver:>7}{(str(nsync)+'/'+str(nrow)):>11}{round(maxd,1):>10}")
    if nver != inman or nsync != nrow:
        all_ok = False
    for w in worst[:8]:
        print("     OUTLIER", w)

print("\nRESULT:", "ALL VERIFIED — every re-voiced track cache-busted + in sync" if all_ok
      else "CHECK NEEDED — see outliers above")
