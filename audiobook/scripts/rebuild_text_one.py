"""Rebuild manifest + read-along + inlined manifest for ONE book (BMM_BOOK) after a text/data
edit (no audio change). Mirrors the tail of revoice.py minus render/master."""
import sys, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config as C
import build_manifest, build_readalong, inline_manifest

build_manifest.main()
shutil.copy2(C.MANIFEST_JSON, C.WEB / "manifest.json")
build_readalong.build_all()
inline_manifest.main()
print(f"rebuilt book {C.BOOK}")
