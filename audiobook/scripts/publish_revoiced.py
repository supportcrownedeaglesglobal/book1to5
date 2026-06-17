"""
publish_revoiced.py — Publish the Books 1-4 Father re-voice to R2, per book.

For each book it determines exactly which tracks changed (those whose segments use the
re-voiced roles decree/shekinaih — the SAME predicate apply_voice_fix used to re-master),
verifies that count against the known re-master count, then calls publish_audio --changed
on just those ids (bumps their ?v=, rebuilds the manifest, uploads the changed mp3s to R2).

If the computed count does NOT match the expected re-master count, it falls back to
publish_audio --all for that book — so we never under-publish and leave stale audio.

  C:\\Python314\\python.exe audiobook\\scripts\\publish_revoiced.py
"""
import sys, os, json, subprocess
from pathlib import Path

HERE  = Path(__file__).resolve().parent
DATA  = HERE.parent / "data"
ROLES = {"decree", "shekinaih"}
EXPECT = {1: 146, 2: 137, 3: 6, 4: 140}          # apply_voice_fix re-master counts (this rollout)

BOOKS = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4]   # default all; pass e.g. "2" to redo one

for book in BOOKS:
    ch  = json.loads((DATA / f"book-{book}" / "chapters.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in ch if any(s.get("role") in ROLES for s in c.get("segments", []))]
    ok  = (len(ids) == EXPECT[book])
    print(f"\n===== BOOK {book}: {len(ids)} changed tracks (expect {EXPECT[book]}) "
          f"{'MATCH' if ok else 'MISMATCH -> publishing ALL (safe)'} =====", flush=True)

    env = dict(os.environ); env["BMM_BOOK"] = str(book)
    cmd = [sys.executable, str(HERE / "publish_audio.py")] + (["--changed", *ids] if ok else ["--all"])
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (r.stdout or "").splitlines():
        if any(k in line for k in ("R2 upload:", "FAIL", "bumped", "nothing to publish", "not staged")):
            print("   " + line, flush=True)
    if r.returncode != 0:
        print(f"   !! publish_audio exited {r.returncode}; stderr tail:", flush=True)
        for line in (r.stderr or "").splitlines()[-5:]:
            print("      " + line, flush=True)
    print(f"===== BOOK {book} done (exit {r.returncode}) =====", flush=True)

print("\n##### ALL BOOKS PUBLISHED #####", flush=True)
