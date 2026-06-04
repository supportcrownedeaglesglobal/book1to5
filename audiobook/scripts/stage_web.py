"""stage_web.py — copy every mastered chapter MP3 named in the manifest into the served
web audio dir (C.WEB = audio/book-N/), plus the manifest itself. master.py writes mp3s to
out/book-N/chapters/; split_appendices stages only the tracks it split, so this fills in
the rest (non-split chapters) and keeps the served set in sync with the manifest.
"""
import shutil, json
import config as C

C.WEB.mkdir(parents=True, exist_ok=True)
man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
n = 0
for ch in man["chapters"]:
    src = C.CHAPTERS / f"{ch['id']}.mp3"
    if src.exists():
        shutil.copy2(src, C.WEB / f"{ch['id']}.mp3")
        n += 1
    else:
        print(f"  !! missing mastered mp3: {ch['id']}")
shutil.copy2(C.MANIFEST_JSON, C.WEB / "manifest.json")
print(f"staged {n}/{len(man['chapters'])} mp3s + manifest to {C.WEB}")
