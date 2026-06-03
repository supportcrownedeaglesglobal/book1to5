"""
place_diagrams.py — Auto-author data/diagrams.json: map each extracted diagram to the
reader paragraph it should follow.

Two stages (robust against the audio=Dec-docx vs images=Nov-PDF divergence):
  1. PAGE -> TRACK. Each playable track is matched to a PDF bookmark (get_toc) to get its
     start page, forced monotonic in book order; an image on page P belongs to the last
     track that starts at or before P. This alone puts every image in the right SECTION
     and prevents the cross-book mis-hits pure text-matching produced.
  2. POSITION WITHIN THE TRACK. Among only that track's paragraphs, pick the one whose
     words best overlap the text just above the image; if that text is uninformative
     (e.g. a continuation screenshot under a bare running-head), fall back to the
     paragraph at the image's fractional page position in the track.

Emits {image, track, after_text, page, how} where after_text is UNIQUE within the track.
Several images may share a paragraph (testimony screenshots) -> the reader stacks them.

  python place_diagrams.py --pdf "<book5 pdf>" --dry
  python place_diagrams.py --pdf "<book5 pdf>"
"""
import argparse, json, re, collections
from pathlib import Path
import fitz
import config as C

OUT = C.ROOT.parent / "images" / "book-5" / "diagrams"
READALONG = C.ROOT.parent / "readalong"
DIAGRAMS_JSON = C.DATA / "diagrams.json"

# Figure groups, assigned by PDF page (from manual review of the extracted candidates):
#   A = core diagrams / teaching figures  (pages up to A_MAX_PAGE)
#   D = photos & cover/section art        (explicit pages)
#   BC = testimony screenshots + text-page captures that duplicate the narration (the rest)
# --groups selects which to place; default "A,D" = the high-value figures, skipping the
# ~120 screenshots/text-dumps. (Pages 280-451 are all the "TESTIMONIES" block.)
A_MAX_PAGE = 262
D_PAGES = {2, 3, 551, 552, 556, 558}


def group_of(page):
    if page in D_PAGES:
        return "D"
    if page <= A_MAX_PAGE:
        return "A"
    return "BC"

STOP = set("""the a an of to and in is on for with that this it as be are was were has have had
will would can could should may might must shall into from by at or but not no nor so than then
their they them his her its our your you we he she him who whom which what when where why how all
any each more most other some such only own same too very just also been being do does did done
these those there here over under out up down off about after before between through during""".split())


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def toks(s):
    return set(w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in STOP)


def load_paras():
    paras = {}
    for jf in sorted(READALONG.glob("*.js")):
        body = jf.read_text(encoding="utf-8").strip()
        data = json.loads(body[body.index("]=") + 2: -1])
        paras[data["id"]] = data["paragraphs"]
    return paras


def page_track_map(doc, tracks, paras):
    """page (1-idx) -> track_id by IDF-weighted content matching. Each page is scored against
    every track by the rarity (IDF) of the words they share, so distinctive names (Jason,
    Davidis, Chai Lin — each in one track) decide the match while common words (which the long
    glossary/appendices share with everything) barely count. Per-page picks are then median-
    smoothed over a ±2 window so a single noisy page can't derail the section."""
    import math
    order = [t["id"] for t in tracks if paras.get(t["id"])]            # playable, book order
    tok = {tid: set().union(*[toks(p["text"]) for p in paras[tid]]) for tid in order}
    order = [tid for tid in order if tok[tid]]
    df = collections.Counter()
    for tid in order:
        for w in tok[tid]:
            df[w] += 1
    N = len(order)
    idf = {w: math.log(1 + N / df[w]) for w in df}                    # rare word -> high weight
    raw = {}                                                          # page -> track index
    for p in range(doc.page_count):
        pt = toks(doc[p].get_text())
        if len(pt) < 5:
            continue
        best = None
        for j, tid in enumerate(order):
            shared = pt & tok[tid]
            if len(shared) < 3:
                continue
            score = sum(idf[w] for w in shared)                       # rarity-weighted overlap
            if best is None or score > best[0]:
                best = (score, j)
        if best:
            raw[p + 1] = best[1]
    page_track, last = {}, 0
    for p in range(1, doc.page_count + 1):
        win = sorted(raw[q] for q in range(p - 2, p + 3) if q in raw)
        if win:
            last = win[len(win) // 2]                                 # median of the ±2 window
        page_track[p] = order[last]
    return page_track


def unique_snippet(text, track_paras, target_idx):
    t = " ".join(text.split())
    others = [" ".join(p["text"].split()) for j, p in enumerate(track_paras) if j != target_idx]
    for n in (80, 60, 45, 32):
        for snip in (t[-n:], t[:n]):
            snip = snip.strip()
            if len(snip) >= 18 and not any(snip in o for o in others):
                return snip
    return t[:60].strip()


def image_anchors(doc):
    """(filename, page, anchor_text) for every kept image, dropping running heads/footers."""
    for pno in range(doc.page_count):
        imgs = doc.get_page_images(pno, full=True)
        if not imgs:
            continue
        H = doc[pno].rect.height
        blocks = [b for b in doc[pno].get_text("blocks") if b[4].strip() and b[6] == 0]
        # drop short blocks hugging the very top/bottom (running heads, page numbers)
        body = [b for b in blocks if not ((b[1] < 70 or b[3] > H - 70) and len(b[4].split()) <= 6)]
        body.sort(key=lambda b: b[1])
        for i, img in enumerate(imgs):
            name = f"p{pno+1:03d}-{i+1}.jpg"
            if not (OUT / name).exists():
                continue
            rects = doc[pno].get_image_rects(img[0])
            top = min((r.y0 for r in rects), default=H / 2)
            above = [b for b in body if b[3] <= top + 2]
            if above:
                anchor = " ".join(b[4] for b in above[-2:])
            else:
                below = [b for b in body if b[1] >= top - 2]
                anchor = " ".join(b[4] for b in below[:1]) if below else (body[0][4] if body else "")
            yield name, pno + 1, " ".join(anchor.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--groups", default="A,D",
                    help="figure groups to place: A=diagrams, D=photos/art, BC=testimonies+text (default A,D)")
    args = ap.parse_args()
    keep = set(g.strip().upper() for g in args.groups.split(","))

    paras = load_paras()
    tracks = json.loads(C.CHAPTERS_JSON.read_text(encoding="utf-8"))
    doc = fitz.open(args.pdf)
    page_track = page_track_map(doc, tracks, paras)
    span = {}                                    # track -> (first_page, last_page) it covers
    for pg, tid in page_track.items():
        s, e = span.get(tid, (pg, pg))
        span[tid] = (min(s, pg), max(e, pg))

    rows, how_counts, per_track, grp_counts = [], collections.Counter(), collections.Counter(), collections.Counter()
    for name, page, anchor in image_anchors(doc):
        grp = group_of(page)
        grp_counts[grp] += 1
        if grp not in keep:
            continue
        tid = page_track.get(page)
        plist = paras.get(tid, []) if tid else []
        if not plist:
            continue
        at = toks(anchor)
        best_i, best_inter = -1, 0
        for pi, p in enumerate(plist):
            inter = len(at & toks(p["text"]))
            if inter > best_inter:
                best_inter, best_i = inter, pi
        if best_inter >= 2:
            idx, how = best_i, "text"
        else:                                   # fractional position by page within track
            sp, ep = span.get(tid, (page, page))
            frac = min(1.0, max(0.0, (page - sp) / max(1, ep - sp)))
            idx, how = round(frac * (len(plist) - 1)), "page"
        rows.append({"image": f"images/book-5/diagrams/{name}", "track": tid,
                     "after_text": unique_snippet(plist[idx]["text"], plist, idx),
                     "page": page, "how": how,
                     "_anchor": anchor[:70], "_para": plist[idx]["text"][:70]})
        how_counts[how] += 1; per_track[tid] += 1

    print(f"candidates by group: " + ", ".join(f"{g}={grp_counts[g]}" for g in ("A", "D", "BC")) +
          f"  | kept groups {sorted(keep)}")
    print(f"placed {len(rows)} images | by text: {how_counts['text']}  by page-position: {how_counts['page']}")
    print(f"tracks receiving images: {len(per_track)} | busiest:")
    for tid, n in per_track.most_common(8):
        print(f"    {n:>2}  {tid}")
    if args.dry:
        print("\n-- 20 samples across the book --")
        for r in rows[::max(1, len(rows)//20)][:20]:
            print(f"\n  {Path(r['image']).name} p{r['page']} [{r['how']}] -> {r['track']}")
            print(f"     anchor: {r['_anchor']}")
            print(f"     after : {r['_para']}")
        print("\n(dry run — data/diagrams.json NOT written)")
        return
    out = [{"image": r["image"], "track": r["track"], "after_text": r["after_text"],
            "page": r["page"], "how": r["how"]} for r in rows]
    DIAGRAMS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(out)} placements -> {DIAGRAMS_JSON}")


if __name__ == "__main__":
    main()
