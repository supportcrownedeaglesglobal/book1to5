"""revoice.py — Re-voice one or more ROLES across books, then re-master + stage + read-along.

After editing the VOICE map in render_kokoro.py for the target role(s), this runs per book,
STRICTLY SEQUENTIAL (never the GPU render and ffmpeg at the same time — that contention
crashes ffmpeg with 0xC0000142 on Windows):
  1. render_kokoro.py --role <roles>    re-synthesize just those role segments (.venv-tts, GPU)
  2. apply_voice_fix.py --roles <roles> re-master ONLY the affected tracks + refresh manifest
  3. stage_web.py                        copy mastered mp3s + manifest -> served audio/book-N/
  4. build_readalong.py                  rebuild read-along timings (durations shifted)
  5. inline_manifest.py                  re-embed the manifest into book-N.html

Audio is staged LOCALLY only — it does NOT upload to R2. Review the staged mp3s, then run
publish_audio.py to bump versions, upload to R2, and deploy the cache-bust.

  C:\\Python314\\python.exe revoice.py --books 5 --roles shekinaih decree
"""
import argparse, os, subprocess, time
from pathlib import Path

REPO    = Path(r"C:\Users\jda61\Documents\book5")
SCRIPTS = REPO / "audiobook" / "scripts"
VENV_PY = REPO / ".venv-tts" / "Scripts" / "python.exe"    # torch + Kokoro (render)
BASE_PY = r"C:\Python314\python.exe"                        # pydub + static_ffmpeg (master/stage/etc.)


def run(py, script, *args, book):
    env = dict(os.environ); env["BMM_BOOK"] = str(book)
    print(f"\n>>> [book {book}] {script} {' '.join(args)}", flush=True)
    r = subprocess.run([str(py), str(SCRIPTS / script), *args], env=env, cwd=str(SCRIPTS))
    if r.returncode != 0:
        raise RuntimeError(f"{script} (book {book}) exited {r.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", nargs="+", required=True, help="book numbers, e.g. --books 5  or  --books 1 2 4")
    ap.add_argument("--roles", nargs="+", required=True, help="roles to re-voice, e.g. --roles shekinaih decree")
    args = ap.parse_args()

    t0, failures = time.time(), []
    for b in args.books:
        print(f"\n========== BOOK {b} — re-voice {args.roles} ==========", flush=True)
        bt = time.time()
        try:
            run(VENV_PY, "render_kokoro.py", "--role", *args.roles, book=b)   # 1 GPU
            run(BASE_PY, "apply_voice_fix.py", "--roles", *args.roles, book=b) # 2 master affected
            run(BASE_PY, "stage_web.py", book=b)                              # 3 stage
            run(BASE_PY, "build_readalong.py", book=b)                        # 4 read-along
            run(BASE_PY, "inline_manifest.py", book=b)                        # 5 embed manifest
            print(f"=== BOOK {b} DONE in {(time.time()-bt)/60:.1f} min ===", flush=True)
        except Exception as e:
            print(f"!!! BOOK {b} FAILED: {e}", flush=True); failures.append(b)

    print(f"\n##### revoice complete in {(time.time()-t0)/60:.1f} min. failures: {failures or 'none'} #####", flush=True)
    print("NEXT: review staged audio in audio/book-N/, then `python publish_audio.py` to upload to R2 + deploy.")


if __name__ == "__main__":
    main()
