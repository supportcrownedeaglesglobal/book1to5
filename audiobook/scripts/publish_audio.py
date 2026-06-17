"""
publish_audio.py — Make (re)generated audio LIVE for the current book (BMM_BOOK).

After chapters are re-mastered + staged into audio/book-N/, this ONE step:
  1. bumps each changed chapter's cache-bust version in data/versions.json
  2. rebuilds the catalog manifest (build_manifest) with the new versions + durations
  3. stages the manifest into audio/book-N/ and re-embeds it into book-N.html
  4. uploads the changed mp3s to Cloudflare R2 (R2_BUCKET/beholdmymessenger-bookN/) via wrangler

So a render driver ends with `publish_audio.py --changed <ids>` and the new audio flows to the
correct R2 folder automatically, with the cache-bust version bumped so the live site serves it.

Auth is the wrangler OAuth login (no secret). Run `wrangler login` once; then this is hands-free.

  BMM_BOOK=5 python publish_audio.py --changed 073-20-unbelief 081-testimonies
  BMM_BOOK=5 python publish_audio.py --all          # (re)publish every mp3 for the book
  BMM_BOOK=5 python publish_audio.py                # auto: mp3s changed since the last publish
  BMM_BOOK=5 python publish_audio.py --dry          # print the plan, change/upload nothing
  BMM_BOOK=5 python publish_audio.py --no-upload    # versions + manifest only, skip R2

After it runs, commit + push the manifest/HTML/versions so the live site picks up the new ?v=.
"""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config as C
import build_manifest
import inline_manifest

MARKER   = C.WEB / ".last_publish"                                   # mtime of the last publish
WRANGLER = Path(os.environ.get("APPDATA", "")) / "npm" / "wrangler.cmd"


def resolve_ids(args):
    """Which chapter ids to (re)publish, and the map of staged mp3s in the served dir."""
    mp3s = {p.stem: p for p in C.WEB.glob("*.mp3")}
    if args.changed:
        missing = [c for c in args.changed if c not in mp3s]
        if missing:
            print(f"  !! not staged in {C.WEB} (skipped): {', '.join(missing)}")
        return [c for c in args.changed if c in mp3s], mp3s
    if args.all:
        return sorted(mp3s), mp3s
    cutoff = MARKER.stat().st_mtime if MARKER.exists() else 0.0      # first run -> everything
    return sorted(k for k, p in mp3s.items() if p.stat().st_mtime > cutoff), mp3s


def bump_versions(ids):
    vfile = C.DATA / "versions.json"
    versions = json.loads(vfile.read_text(encoding="utf-8")) if vfile.exists() else {}
    for cid in ids:
        versions[cid] = int(versions.get(cid, 1)) + 1
    vfile.parent.mkdir(parents=True, exist_ok=True)
    vfile.write_text(json.dumps(versions, ensure_ascii=False, indent=1), encoding="utf-8")
    return versions


def upload(local: Path, key: str):
    obj = f"{C.R2_BUCKET}/{key}"
    env = dict(os.environ); env["CLOUDFLARE_ACCOUNT_ID"] = C.R2_ACCOUNT
    wr = str(WRANGLER) if WRANGLER.exists() else "wrangler"
    r = subprocess.run([wr, "r2", "object", "put", obj, f"--file={local}",
                        "--remote", "--content-type", "audio/mpeg",
                        "--cache-control", "public, max-age=31536000, immutable"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = ((r.stderr or r.stdout) or "").strip().splitlines()
    return r.returncode == 0, (tail[-1] if tail else "")


def main():
    for _s in (sys.stdout, sys.stderr):                  # Windows console is cp1252; wrangler
        try: _s.reconfigure(encoding="utf-8", errors="replace")   # emits emoji -> encode-safe
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--changed", nargs="*", help="explicit chapter ids whose audio changed")
    ap.add_argument("--all", action="store_true", help="publish every staged mp3 for this book")
    ap.add_argument("--dry", action="store_true", help="print the plan, change/upload nothing")
    ap.add_argument("--no-upload", action="store_true", help="bump versions + manifest only, skip R2")
    args = ap.parse_args()

    ids, mp3s = resolve_ids(args)
    print(f"book {C.BOOK}: {len(ids)} chapter(s) to publish -> R2 {C.R2_BUCKET}/{C.R2_FOLDER}/")
    for c in ids[:20]:
        print("   ", c)
    if len(ids) > 20:
        print(f"    ... +{len(ids) - 20} more")
    if not ids:
        print("nothing to publish."); return
    if args.dry:
        print("\n(dry run — no version bump, no manifest rebuild, no upload)"); return

    bump_versions(ids)
    print(f"bumped {len(ids)} cache-bust version(s) in {C.DATA / 'versions.json'}")

    build_manifest.main()                                    # new versions + durations
    shutil.copy2(C.MANIFEST_JSON, C.WEB / "manifest.json")   # stage the served manifest
    inline_manifest.main()                                   # re-embed into book-N.html

    if args.no_upload:
        print("--no-upload: skipped R2 upload.")
    else:
        ok = fail = 0
        for cid in ids:
            local = mp3s.get(cid) or (C.WEB / f"{cid}.mp3")
            good, msg = upload(local, f"{C.R2_FOLDER}/{cid}.mp3")
            if good: ok += 1;  print(f"  OK   {C.R2_FOLDER}/{cid}.mp3")
            else:    fail += 1; print(f"  FAIL {C.R2_FOLDER}/{cid}.mp3 :: {msg}")
        print(f"R2 upload: {ok} ok, {fail} failed")
        if fail:
            print("  (if it says not authenticated, run:  wrangler login )")

    MARKER.write_text(str(time.time()), encoding="utf-8")
    print("\nNEXT (deploy the cache-bust): commit + push the manifest/HTML/versions, e.g.")
    print("  git add audio readalong book-*.html audiobook/data && git commit -m \"publish audio\" "
          "&& git push origin HEAD:main")


if __name__ == "__main__":
    main()
