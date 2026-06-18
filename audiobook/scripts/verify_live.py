"""
verify_live.py — Confirm Books 1-5 are correctly LIVE (not just staged locally).

Per book:
  1. Fetch the deployed Cloudflare Pages manifest and confirm it is byte-identical (chapter
     count + every version) to the local served manifest -> the latest deploy is live.
  2. For EVERY re-voiced track (decree/shekinaih), HEAD the R2 object and confirm it exists
     with a Content-Length equal to the local new-master mp3 -> the NEW audio is live (not stale).
  3. Spot-check a few NON-re-voiced tracks are still present on R2.

Network needs the sandbox disabled. Run:
  C:\\Python314\\python.exe audiobook\\scripts\\verify_live.py
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
DATA = ROOT / "audiobook" / "data"
LIVE = "https://crownedeaglesglobal-beholdmymessengerseries-audio.com"
R2   = "https://pub-163ec17fb5564d7a9193345f48fea08f.r2.dev"
ROLES = {"decree", "shekinaih"}


def fetch(url, head=False, timeout=30, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD" if head else "GET",
                                         headers={"User-Agent": "bmm-verify"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers), (b"" if head else r.read())
        except Exception as e:
            if i == tries - 1:
                return None, {}, str(e)
    return None, {}, "??"


def paths(b):
    if b == 5:
        return dict(man=ROOT/"audio/book-5/manifest.json", chap=DATA/"chapters.json",
                    web=ROOT/"audio/book-5", r2="beholdmymessenger-book5",
                    live=f"{LIVE}/audio/book-5/manifest.json")
    return dict(man=ROOT/f"audio/book-{b}/manifest.json", chap=DATA/f"book-{b}/chapters.json",
                web=ROOT/f"audio/book-{b}", r2=f"beholdmymessenger-book{b}",
                live=f"{LIVE}/audio/book-{b}/manifest.json")


grand_issues = []
for b in (1, 2, 3, 4, 5):
    P = paths(b)
    local = {c["id"]: c for c in json.loads(P["man"].read_text(encoding="utf-8"))["chapters"]}
    chap  = json.loads(P["chap"].read_text(encoding="utf-8"))
    changed = sorted({c["id"] for c in chap if any(s.get("role") in ROLES for s in c.get("segments", []))})

    print(f"\n========== BOOK {b} ==========", flush=True)

    # 1) live manifest vs local
    st, hd, body = fetch(P["live"])
    if st != 200:
        print(f"  LIVE manifest: HTTP {st} !! {body}"); grand_issues.append((b, "live manifest unreachable"));
    else:
        try:
            liveman = {c["id"]: c for c in json.loads(body)["chapters"]}
            same_count = len(liveman) == len(local)
            vmismatch = [cid for cid in local if liveman.get(cid, {}).get("version") != local[cid].get("version")]
            vbumped = sum(1 for cid in changed if int(liveman.get(cid, {}).get("version", 1)) >= 2)
            print(f"  LIVE manifest: HTTP 200  chapters live={len(liveman)} local={len(local)} "
                  f"same={same_count}  version-mismatches={len(vmismatch)}  changed v>=2 live={vbumped}/{len(changed)}")
            if not same_count or vmismatch:
                grand_issues.append((b, f"live manifest stale: count_same={same_count}, vmismatch={len(vmismatch)}"))
                for cid in vmismatch[:5]:
                    print(f"     stale ver: {cid} live={liveman.get(cid,{}).get('version')} local={local[cid].get('version')}")
            if vbumped != len(changed):
                grand_issues.append((b, f"only {vbumped}/{len(changed)} changed tracks show v>=2 live"))
        except Exception as e:
            print(f"  LIVE manifest parse error: {e}"); grand_issues.append((b, f"live manifest parse {e}"))

    # 2) every re-voiced track: R2 object exists + size == local new-master
    miss = badsize = okc = 0
    for cid in changed:
        lp = P["web"] / f"{cid}.mp3"
        lsize = lp.stat().st_size if lp.exists() else -1
        st2, hd2, _ = fetch(f"{R2}/{P['r2']}/{cid}.mp3", head=True)
        rsize = int(hd2.get("Content-Length", -1)) if st2 == 200 else -1
        if st2 != 200:
            miss += 1; grand_issues.append((b, f"R2 MISSING {cid} (http {st2})"))
            print(f"   !! R2 MISSING {cid} http={st2}")
        elif rsize != lsize:
            badsize += 1; grand_issues.append((b, f"R2 SIZE MISMATCH {cid} r2={rsize} local={lsize}"))
            print(f"   !! R2 SIZE {cid} r2={rsize} local={lsize}")
        else:
            okc += 1
    print(f"  R2 re-voiced audio: {okc}/{len(changed)} present & size-matched  (missing={miss}, badsize={badsize})")

    # 3) spot-check non-changed tracks still present
    nonchanged = [cid for cid in local if cid not in set(changed)][:5]
    nc_ok = 0
    for cid in nonchanged:
        st3, _, _ = fetch(f"{R2}/{P['r2']}/{cid}.mp3", head=True)
        if st3 == 200: nc_ok += 1
        else: print(f"   !! non-changed track MISSING on R2: {cid} http={st3}"); grand_issues.append((b, f"R2 missing non-changed {cid}"))
    print(f"  R2 non-changed spot-check: {nc_ok}/{len(nonchanged)} present")

print("\n\n################ SUMMARY ################")
if not grand_issues:
    print("ALL 5 BOOKS LIVE + CORRECT: deployed manifests current, every re-voiced track present on R2 with matching size, no stale versions.")
else:
    print(f"{len(grand_issues)} ISSUE(S):")
    for b, msg in grand_issues:
        print(f"  book {b}: {msg}")
