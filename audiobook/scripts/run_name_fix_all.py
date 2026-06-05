"""run_name_fix_all.py — Apply 'J Aaron K David' to ALL FIVE books' audio.

Per book, STRICTLY SEQUENTIAL (never the GPU render and ffmpeg at the same time — that
contention crashes ffmpeg with 0xC0000142 on Windows):
  1. render_kokoro.py --pattern   re-synthesize only the clips naming the messenger (.venv-tts)
  2. apply_name_fix.py            re-master just the affected tracks + refresh manifest durations
  3. stage_web.py                 copy mastered mp3s + manifest -> served audio/book-N/
  4. build_readalong.py           rebuild read-along timings (durations shifted slightly)
  5. inline_manifest.py           re-embed the manifest into book-N.html

Each book is isolated: a failure is logged and the next book still runs.
Run with the base interpreter:  C:\\Python314\\python.exe run_name_fix_all.py
"""
import os, subprocess, time
from pathlib import Path

REPO    = Path(r"C:\Users\jda61\Documents\book5")
SCRIPTS = REPO / "audiobook" / "scripts"
VENV_PY = REPO / ".venv-tts" / "Scripts" / "python.exe"   # torch + Kokoro (render)
BASE_PY = r"C:\Python314\python.exe"                       # pydub + static_ffmpeg (master/stage/etc.)
PATTERN = r"(AARON|Aaron)\s+K\.?\s+(DAVID|David)"

def run(py, script, *args, book=None):
    env = dict(os.environ)
    if book is not None:
        env["BMM_BOOK"] = str(book)
    print(f"\n>>> [book {book}] {script} {' '.join(args)}", flush=True)
    r = subprocess.run([str(py), str(SCRIPTS / script), *args], env=env, cwd=str(SCRIPTS))
    if r.returncode != 0:
        raise RuntimeError(f"{script} (book {book}) exited {r.returncode}")

failures = []
t0 = time.time()
for b in ["1", "2", "3", "4", "5"]:
    print(f"\n===================== BOOK {b} =====================", flush=True)
    bt = time.time()
    try:
        run(VENV_PY, "render_kokoro.py", "--pattern", PATTERN, book=b)   # 1
        run(BASE_PY, "apply_name_fix.py", book=b)                        # 2
        run(BASE_PY, "stage_web.py", book=b)                             # 3
        run(BASE_PY, "build_readalong.py", book=b)                       # 4
        run(BASE_PY, "inline_manifest.py", book=b)                       # 5
        print(f"=== BOOK {b} DONE in {(time.time()-bt)/60:.1f} min ===", flush=True)
    except Exception as e:
        print(f"!!! BOOK {b} FAILED: {e}", flush=True)
        failures.append(b)

print(f"\n##### ALL BOOKS COMPLETE in {(time.time()-t0)/60:.1f} min. "
      f"failures: {failures or 'none'} #####", flush=True)
