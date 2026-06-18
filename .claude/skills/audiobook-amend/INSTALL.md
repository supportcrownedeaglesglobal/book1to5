# Installing & using the `audiobook-amend` skill

This skill is **already published** in this repository at
`.claude/skills/audiobook-amend/SKILL.md` and pushed to GitHub
(`https://github.com/supportcrownedeaglesglobal/book1to5`, branch `main`).
A Claude Code skill is just a folder with a `SKILL.md` (YAML front-matter + instructions);
Claude auto-discovers it from a `.claude/skills/` directory. Here is how to use it now and how
to make it available elsewhere.

---

## Option 1 — Project-level (already active in this repo)
Nothing to install. When you (or Claude Code) work **inside a clone of this repo**, the skill is
auto-discovered from `.claude/skills/`. Just describe the change ("re-voice the scripture
narrator", "fix this typo in Book 2", "add the Book 4 figures") or invoke it directly:

```
/audiobook-amend
```

## Option 2 — User-level (available in EVERY project, any folder)
Copy the skill into your personal Claude config so it loads in all sessions:

**Windows (PowerShell):**
```powershell
$src = "C:\Users\jda61\Documents\book5\.claude\skills\audiobook-amend"
$dst = "$env:USERPROFILE\.claude\skills\audiobook-amend"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\*" $dst -Recurse -Force
```

**macOS / Linux:**
```bash
mkdir -p ~/.claude/skills/audiobook-amend
cp -r /path/to/book5/.claude/skills/audiobook-amend/* ~/.claude/skills/audiobook-amend/
```

Start a new Claude Code session to pick it up. (Note: the *runbook commands* assume this repo's
scripts and paths, so the skill is most useful when working on the audiobook repo itself.)

## Option 3 — On a fresh machine / new clone
```bash
git clone https://github.com/supportcrownedeaglesglobal/book1to5.git
cd book1to5
```
The skill is at `.claude/skills/audiobook-amend/` and auto-loads when you work in this directory.
Optionally also copy it user-level (Option 2).

---

## Prerequisites to actually RUN the pipeline the skill describes
The skill drives this repo's `audiobook/scripts/`. To execute them you need:

| Need | What |
|------|------|
| **Base Python** | `C:\Python314\python.exe` with `pydub`, `static_ffmpeg`, `PyMuPDF` (`fitz`), `Pillow` — runs mastering, web build, diagram + verify scripts |
| **GPU TTS venv** | `.venv-tts` with `torch` (CUDA build) + `kokoro` — **only** needed to re-render audio (`render_kokoro.py`) |
| **wrangler** | `npm i -g wrangler`, then **`wrangler login`** (browser OAuth — never paste a key) — for R2 uploads |
| **Source PDFs** | `C:\Users\jda61\OneDrive\Desktop\5books26Dec\` (Book 1–5 PDFs) — for diagram extraction/placement only |
| **Git push access** | to `supportcrownedeaglesglobal/book1to5` — deploys go `changev3 → main`, then Cloudflare Pages auto-builds |

You do **not** need the GPU venv, wrangler, or the PDFs for text/read-along-only edits — only the
base Python.

## Verify it's loaded
In a session in this repo, type `/` and look for **`audiobook-amend`**, or ask "what skills are
available?". Then invoke `/audiobook-amend` or just describe the amendment.

## Keeping it up to date
Edit `.claude/skills/audiobook-amend/SKILL.md`, then `git commit` + `git push` (on `changev3`,
then `changev3:main`). If you installed it user-level (Option 2), re-copy after pulling.
