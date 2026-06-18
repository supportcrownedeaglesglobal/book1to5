"""Repair PDF line-break hyphenation artifacts ("YAH- WEH" -> "YAHWEH") in chapters.json + the
diagram after_text anchors (kept in sync so figures still match), and drop the junk Book-2
"138-section" chapter (title "."). --dry shows sample joins without writing."""
import json, re, sys
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5"); DATA = ROOT / "audiobook" / "data"
DRY = "--dry" in sys.argv
# letter, hyphen, whitespace, letter  -> join (a real "Anti-Christ" has NO space, so it's preserved)
PAT = re.compile(r'([A-Za-z])-\s+([A-Za-z])')
samples = []

def fix(s):
    n = 0
    def r(m):
        nonlocal n; n += 1
        if len(samples) < 25:
            a = max(0, m.start() - 12); samples.append(s[a:m.end() + 10].replace("\n", " "))
        return m.group(1) + m.group(2)
    return PAT.sub(r, s), n

def dd(b): return DATA if b == 5 else DATA / f"book-{b}"

grand = 0
for b in (1, 2, 3, 4, 5):
    cf = dd(b) / "chapters.json"
    ch = json.loads(cf.read_text(encoding="utf-8"))
    removed = 0
    if b == 2:
        n0 = len(ch); ch = [c for c in ch if c.get("id") != "138-section"]; removed = n0 - len(ch)
    cnt = 0
    for c in ch:
        nt, n1 = fix(c.get("title", "")); c["title"] = nt; cnt += n1
        for s in c.get("segments", []):
            nx, n2 = fix(s.get("text", "")); s["text"] = nx; cnt += n2
    df = dd(b) / "diagrams.json"
    dj = json.loads(df.read_text(encoding="utf-8"))
    dc = 0
    for d in dj:
        na, n3 = fix(d.get("after_text", "")); d["after_text"] = na; dc += n3
    if not DRY:
        cf.write_text(json.dumps(ch, ensure_ascii=False, indent=1), encoding="utf-8")
        df.write_text(json.dumps(dj, ensure_ascii=False, indent=1), encoding="utf-8")
    grand += cnt + dc
    print(f"book {b}: dehyphenated chapters={cnt} diagrams_after_text={dc} removed_138_section={removed}")

print(f"\nTOTAL joins: {grand}   ({'DRY RUN - nothing written' if DRY else 'WRITTEN'})")
print("\nSAMPLE joins (context -> the matched span gets its hyphen+space removed):")
for s in samples[:25]:
    print("   ", repr(s))
