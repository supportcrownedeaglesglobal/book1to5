"""
extract_diagrams.py — Pull candidate CONTENT images from the Book 5 PDF for the read-along
reader's inline figures.

It skips decorative images (ones that repeat across many pages — borders/watermarks), very
small images, and thin rules; de-duplicates re-encoded copies (average-hash); decodes every
image through a MuPDF pixmap (robust to odd colorspaces/codecs in a "compressed" PDF) and
web-optimizes it (cap long side, JPEG) into images/book-5/diagrams/.

Outputs:
  images/book-5/diagrams/p<page>-<i>.jpg     the optimized candidate images
  data/diagrams_index.json                   inventory [{file,page,w,h,context}] for the
                                             curation pass that authors data/diagrams.json
  (with --contact) audiobook/out/diagram_contact/sheet-NN.png   labelled thumbnail grids

The CURATION step (separate, with the user) authors data/diagrams.json — each entry
{image, track, after_text} — and build_readalong.py attaches the image to the matching
paragraph. This script only produces candidates; it never edits diagrams.json.

Run (3.14 env, needs PyMuPDF + Pillow):
  python extract_diagrams.py --pdf "<path to Book 5 pdf>" --contact
"""
import argparse, io, json, collections, re
from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont
import config as C

OUT = C.IMAGES / "diagrams"
INDEX = C.DATA / "diagrams_index.json"
CONTACT = C.ROOT / "out" / "diagram_contact"

REPEAT_PAGES = 4      # an image on >= this many pages is decorative (border/watermark)
MIN_DIM = 250         # drop images whose width OR height is under this (px)
MAX_LONG = 1200       # web-optimize: cap the long side at this many px
JPEG_Q = 82
ASPECT_MAX = 8.0      # drop thin rules/dividers


def ahash(im):
    g = im.convert("L").resize((8, 8))
    px = list(g.getdata()); avg = sum(px) / 64.0
    bits = 0
    for i, p in enumerate(px):
        if p >= avg:
            bits |= (1 << i)
    return bits


def ham(a, b):
    return bin(a ^ b).count("1")


def pil_from_xref(doc, xref):
    """Decode an embedded image to an RGB PIL image via a MuPDF pixmap (codec-agnostic)."""
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha or pix.n > 3 or pix.colorspace is None or pix.colorspace.n != 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)   # normalize CMYK/gray/alpha → RGB
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def page_context(doc, pno):
    txt = " ".join(doc[pno].get_text().split())
    return txt[:300]


def extract(pdf):
    doc = fitz.open(pdf)
    # 1) which xrefs are decorative (appear on many pages)?
    xref_pages = collections.defaultdict(set)
    for pno in range(doc.page_count):
        for img in doc.get_page_images(pno, full=True):
            xref_pages[img[0]].add(pno)
    decorative = {x for x, ps in xref_pages.items() if len(ps) >= REPEAT_PAGES}

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()                          # clean re-run

    kept_hashes, index, seen = [], [], set()
    for pno in range(doc.page_count):
        for i, img in enumerate(doc.get_page_images(pno, full=True)):
            xref = img[0]
            if xref in decorative or xref in seen:
                continue
            seen.add(xref)
            try:
                im = pil_from_xref(doc, xref)
            except Exception as e:
                print(f"  skip xref {xref} (decode failed: {e})"); continue
            w, h = im.size
            if w < MIN_DIM or h < MIN_DIM:
                continue
            if max(w, h) / max(1, min(w, h)) > ASPECT_MAX:
                continue
            hsh = ahash(im)
            if any(ham(hsh, k) <= 4 for k in kept_hashes):
                continue                    # near-duplicate of one we already kept
            kept_hashes.append(hsh)
            if max(im.size) > MAX_LONG:
                im.thumbnail((MAX_LONG, MAX_LONG))
            name = f"p{pno+1:03d}-{i+1}.jpg"
            im.save(OUT / name, "JPEG", quality=JPEG_Q, optimize=True)
            index.append({"file": f"images/book-{C.BOOK}/diagrams/{name}", "page": pno + 1,
                          "w": w, "h": h, "context": page_context(doc, pno)})
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"extracted {len(index)} content images -> {OUT}")
    print(f"inventory -> {INDEX}")
    return index


def make_contact(index, per_row=6, rows=6, thumb=200, pad=12, label=26):
    CONTACT.mkdir(parents=True, exist_ok=True)
    for f in CONTACT.glob("*.png"):
        f.unlink()
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except Exception:
        font = ImageFont.load_default()
    per_sheet = per_row * rows
    cell_w, cell_h = thumb + pad, thumb + pad + label
    sheets = 0
    for s in range(0, len(index), per_sheet):
        chunk = index[s:s + per_sheet]
        cols = per_row
        rws = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell_w + pad, rws * cell_h + pad), (24, 22, 34))
        d = ImageDraw.Draw(sheet)
        for k, entry in enumerate(chunk):
            r, c = divmod(k, cols)
            x, y = pad + c * cell_w, pad + r * cell_h
            try:
                im = Image.open(C.ROOT.parent / entry["file"]); im.thumbnail((thumb, thumb))
                sheet.paste(im, (x + (thumb - im.width) // 2, y + (thumb - im.height) // 2))
            except Exception:
                pass
            tag = f'p{entry["page"]}  {Path(entry["file"]).name}'
            d.text((x, y + thumb + 4), tag, fill=(235, 220, 180), font=font)
        out = CONTACT / f"sheet-{sheets+1:02d}.png"
        sheet.save(out, "PNG")
        print(f"  contact sheet -> {out}  ({len(chunk)} images)")
        sheets += 1
    print(f"{sheets} contact sheet(s) in {CONTACT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--contact", action="store_true", help="also write labelled thumbnail grids")
    args = ap.parse_args()
    idx = extract(args.pdf)
    if args.contact:
        make_contact(idx)
