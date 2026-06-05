"""List every layer in the Book 1 cover PSD so we can identify the dove, flames, and text
layers to extract as transparent PNGs for the website hero."""
import sys
from psd_tools import PSDImage

PSD = r"C:\Users\jda61\OneDrive\Desktop\5books26Dec\Covers\Book 1\Book 1 Cover.psd"
p = PSDImage.open(PSD)
print(f"PSD size: {p.size}  color_mode: {p.color_mode}")
print("-" * 70)

def walk(layers, depth=0):
    for l in layers:
        pad = "  " * depth
        try:
            bbox = l.bbox
        except Exception:
            bbox = None
        print(f"{pad}- {l.name!r} | kind={l.kind} | visible={l.visible} | bbox={bbox}")
        if l.is_group():
            walk(list(l), depth + 1)

walk(list(p))
