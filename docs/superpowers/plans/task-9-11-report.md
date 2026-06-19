# Task 9-11 Report — Guide-me widget (frontend)

**Status:** complete  
**Branch:** changev4 (no push)

**Changes:**
- `functions/api/_guide.js` — added `url` field to plan items (additive, 1 line)
- `assets/guide.css` — created (floating panel + FAB styles, gold/dark theme)
- `assets/guide.js` — created (chat widget IIFE, Turnstile, localStorage)
- `index.html`, `book-1..5.html` — wired snippet before `</body>` (6 files)

**npm test:** 8/8 passed (5 test files)  
**node --check assets/guide.js:** exit 0 (no syntax errors)  
**Wired files:** index.html, book-1.html, book-2.html, book-3.html, book-4.html, book-5.html  
**Concern:** Turnstile siteKey is the CF test key (`1x00000000000000000000AA`) — swap for real key before production deploy.
