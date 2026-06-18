"""One-off: apply safe reader fixes uniformly across book-1..5.html (the reader JS is duplicated)."""
from pathlib import Path

ROOT = Path(r"C:\Users\jda61\Documents\book5")
REPLACES = [
    ("t<ps[j].end",   "t<=ps[j].end"),                 # sync: last paragraph stays highlighted to exact end
    ('src="${src}"',  'src="${escHtml(src)}"'),         # escape diagram src in read-along figure markup
]
CSS = ".rate,.sleep,.rpt{min-width:44px}"               # ensure 44px tap target width (elderly/mobile)
MARK = "/* a11y: 44px option-button width */"

for b in (1, 2, 3, 4, 5):
    f = ROOT / f"book-{b}.html"
    s = f.read_text(encoding="utf-8")
    rep = {}
    for old, new in REPLACES:
        c = s.count(old)
        rep[old] = c
        if c:
            s = s.replace(old, new)
    if MARK not in s:
        i = s.rfind("</style>")
        if i != -1:
            s = s[:i] + f"\n{MARK}\n{CSS}\n" + s[i:]
            rep["css_appended"] = True
    f.write_text(s, encoding="utf-8")
    print(f"book {b}: {rep}")
print("done")
