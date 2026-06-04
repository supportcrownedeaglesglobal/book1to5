"""make_player.py — Generate book-N.html from book-5.html (the reference player page),
swapping only the per-book bits: cover/image paths, title + subtitle, the audio base URL,
and the read-along directory. Run inline_manifest.py afterwards to embed the book's manifest.

  BMM_BOOK=3 python make_player.py                       # local audio (audio/book-3/)
  BMM_BOOK=3 python make_player.py --audio-base "https://<id>.r2.dev/beholdmymessenger-book3"

book-5.html itself is the template and is never regenerated.
"""
import argparse, re
import config as C

TEMPLATE = C.REPO / "book-5.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-base", default="",
                    help="AUDIO_BASE_URL; empty = serve local audio/book-N/ (works on file://)")
    args = ap.parse_args()
    N = C.BOOK
    if N == "5":
        raise SystemExit("book-5.html is the template — not regenerating it")

    parts = re.split(r"\s*—\s*", C.BOOK_TITLE, maxsplit=1)
    main_t = parts[0]                              # "Behold My Messenger 3"
    sub_t = parts[1] if len(parts) > 1 else ""     # "Behold My Names"
    subtitle = C.BOOK_SUBTITLE                      # "The Seven Names of the Trinity"

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("images/book-5/", f"images/book-{N}/")
    html = html.replace("Behold My Messenger 5", main_t)
    html = html.replace("The Resurrection of the Dead", sub_t)
    html = html.replace("The doctrine of the power of the age to come", subtitle)
    # audio source base (local vs R2)
    html = re.sub(r'const AUDIO_BASE_URL = "[^"]*";',
                  f'const AUDIO_BASE_URL = "{args.audio_base}";', html, count=1)
    # read-along files nest under readalong/book-N/ for books 1-4 (Book 5 is flat)
    html = html.replace("s.src='readalong/'+id", f"s.src='readalong/book-{N}/'+id")

    C.PLAYER_HTML.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {C.PLAYER_HTML}")
    print(f"  title   : {main_t} — {sub_t}")
    print(f"  subtitle: {subtitle}")
    print(f"  audio   : {args.audio_base or 'local audio/book-'+N+'/'}")
    print("  NEXT: BMM_BOOK={} python inline_manifest.py  (embed the manifest)".format(N))


if __name__ == "__main__":
    main()
