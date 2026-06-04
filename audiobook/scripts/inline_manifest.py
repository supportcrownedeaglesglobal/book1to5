"""
inline_manifest.py — Embed the served manifest into index.html as a fallback.

The page fetches audio/book-5/manifest.json at runtime (so a live host always gets
the latest), but fetch() is blocked under file:// and offline. To make the page
work everywhere, index.html carries a copy of the manifest in
  <script type="application/json" id="manifest-fallback"> ... </script>
and init() falls back to it when fetch fails.

Run this whenever the manifest changes (after master.py / build_manifest.py /
split_appendices.py) to refresh that embedded copy:
  python inline_manifest.py
"""
import io, re
import config as C

INDEX = C.ROOT.parent / "book-5.html"   # the Book 5 player (index.html is now the multi-book landing page)
MANIFEST = C.ROOT.parent / "audio" / "book-5" / "manifest.json"
OPEN = '<script type="application/json" id="manifest-fallback">'
CLOSE = "</script>"


def main():
    html = io.open(INDEX, encoding="utf-8").read()
    manifest = io.open(MANIFEST, encoding="utf-8").read().rstrip()
    block = f"{OPEN}\n{manifest}\n{CLOSE}"

    if OPEN in html:                                   # replace existing block
        start = html.index(OPEN)
        end = html.index(CLOSE, start) + len(CLOSE)
        html = html[:start] + block + html[end:]
        action = "replaced"
    else:                                              # insert before main script
        anchor = '<script>\nconst M_URL'
        if anchor not in html:
            raise SystemExit("anchor '<script>\\nconst M_URL' not found in index.html")
        html = html.replace(anchor, block + "\n\n" + anchor, 1)
        action = "inserted"

    io.open(INDEX, "w", encoding="utf-8", newline="\n").write(html)
    # report size of the embedded manifest for sanity
    import json
    n = len(json.loads(manifest)["chapters"])
    print(f"{action} embedded manifest ({n} chapters, {len(manifest)} bytes) in {INDEX}")


if __name__ == "__main__":
    main()
