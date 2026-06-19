# Installing & using the `book-site-create` skill

This skill is **published** in this repository at
`.claude/skills/book-site-create/SKILL.md` and pushed to GitHub
(`https://github.com/supportcrownedeaglesglobal/book1to5`, branch `main`).
A Claude Code skill is just a folder with a `SKILL.md` (YAML front-matter + instructions);
Claude auto-discovers it from a `.claude/skills/` directory.

It is the **greenfield** companion to **`audiobook-amend`**: use `book-site-create` to stand up a
**new** book (e.g. Book 6, or a new series) from a manuscript; use `audiobook-amend` to **change**
an already-built book. Both are most useful when working inside this repo.

---

## Option 1 — Project-level (already active in this repo)
Nothing to install. When you (or Claude Code) work **inside a clone of this repo**, the skill is
auto-discovered from `.claude/skills/`. Just describe the goal ("create Book 6", "make a text-only
e-book page for the new manuscript", "bootstrap a new audiobook repo") or invoke it directly:

```
/book-site-create
```

## Option 2 — User-level (available in EVERY project, any folder)
Copy the skill into your personal Claude config so it loads in all sessions:

**Windows (PowerShell):**
```powershell
$src = "C:\Users\jda61\Documents\book5\.claude\skills\book-site-create"
$dst = "$env:USERPROFILE\.claude\skills\book-site-create"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\*" $dst -Recurse -Force
```

**macOS / Linux:**
```bash
mkdir -p ~/.claude/skills/book-site-create
cp -r /path/to/book5/.claude/skills/book-site-create/* ~/.claude/skills/book-site-create/
```

Start a new Claude Code session to pick it up. (The *runbook commands* assume this repo's scripts
and paths, so the skill is most useful when working on the audiobook repo itself.)

## Option 3 — On a fresh machine / new clone
```bash
git clone https://github.com/supportcrownedeaglesglobal/book1to5.git
cd book1to5
```
The skill is at `.claude/skills/book-site-create/` and auto-loads when you work in this directory.

---

## Prerequisites to actually RUN the pipeline
See **§3 of `SKILL.md`** for the full list. In short:

| Need | For | What |
|------|-----|------|
| **A new manuscript** | both paths | the new book's `.docx` (+ PDF for figures) placed in `SRC` (`config.py`). **The skill stops and asks if it's missing.** |
| **Base Python** | both paths | `C:\Python314\python.exe` + `python-docx`, `pydub`, `static_ffmpeg`, `audioop-lts`, `PyMuPDF`, `Pillow` |
| **GPU TTS venv** | audiobook only | `.venv-tts` with CUDA `torch` + `kokoro` (for `render_kokoro.py`) |
| **wrangler** | audiobook deploy | `npm i -g wrangler`, then `wrangler login` (browser OAuth — never paste a key) |

The text-only e-book path needs only the base Python (no GPU, no wrangler, no R2).

## Verify it's loaded
In a session in this repo, type `/` and look for **`book-site-create`**, or ask "what skills are
available?". Then invoke `/book-site-create` or just describe the new book.

## Keeping it up to date
Edit `.claude/skills/book-site-create/SKILL.md`, then `git commit` + `git push` (on `changev3`,
then `changev3:main`). If you installed it user-level (Option 2), re-copy after pulling.
