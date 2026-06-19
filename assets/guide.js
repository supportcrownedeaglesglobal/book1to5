// "Guide me" floating AI reading companion. Usage: window.BMMGuide.mount({siteKey})
(function () {
  const KEY = "bmm_guide";
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || { history: [], plan: [] }; } catch { return { history: [], plan: [] }; } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify({ history: s.history.slice(-12), plan: s.plan || [] })); } catch (e) {} };
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function mount({ siteKey }) {
    const state = load();
    const fab = el("button", "guide-fab", "✦ Guide me");
    fab.setAttribute("aria-label", "Open the reading guide");
    const panel = el("div", "guide-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Reading guide");
    panel.innerHTML =
      '<div class="guide-head"><span>Your reading guide</span><button class="guide-x" type="button" aria-label="Close">×</button></div>' +
      '<div class="guide-log" aria-live="polite"></div>' +
      '<form class="guide-form"><input class="guide-in" type="text" autocomplete="off" placeholder="What are you facing today?" aria-label="Tell the guide what you are facing" /><button class="guide-send" type="submit">Send</button></form>' +
      '<div class="guide-ts" style="display:none"></div>';
    document.body.appendChild(fab);
    document.body.appendChild(panel);
    const log = panel.querySelector(".guide-log");
    const form = panel.querySelector(".guide-form");
    const input = panel.querySelector(".guide-in");
    const tsHost = panel.querySelector(".guide-ts");
    let tsId = null, busy = false;

    const addMsg = (text, who) => { const m = el("div", "guide-msg" + (who === "me" ? " me" : "")); m.textContent = text; log.appendChild(m); log.scrollTop = log.scrollHeight; return m; };
    const addCards = (chapters) => { (chapters || []).forEach((c) => { const a = el("a", "guide-card"); a.href = c.url || "#"; a.innerHTML = "🎧 <b>Book " + esc(c.book) + "</b> — " + esc(c.title); log.appendChild(a); }); log.scrollTop = log.scrollHeight; };
    const addPlan = (plan) => { if (!plan || !plan.length) return; const ol = el("ol", "guide-plan"); plan.forEach((p) => { const li = el("li"); li.innerHTML = '<a href="' + esc(p.url || "#") + '">' + esc(p.title) + "</a>" + (p.why ? " — " + esc(p.why) : ""); ol.appendChild(li); }); log.appendChild(ol); log.scrollTop = log.scrollHeight; };

    state.history.forEach((h) => addMsg(h.content, h.role === "user" ? "me" : "bot"));
    if (!state.history.length) addMsg("Tell me what you're facing today — grief, doubt, fear, or simply where to begin — and I'll point you to the right chapters and a plan to listen.", "bot");

    const openPanel = () => { panel.classList.add("open"); if (window.turnstile && tsId === null) { try { tsId = window.turnstile.render(tsHost, { sitekey: siteKey, size: "invisible" }); } catch (e) {} } input.focus(); };
    const closePanel = () => panel.classList.remove("open");
    fab.addEventListener("click", () => (panel.classList.contains("open") ? closePanel() : openPanel()));
    panel.querySelector(".guide-x").addEventListener("click", closePanel);

    const getToken = () => new Promise((resolve) => {
      if (!window.turnstile || tsId === null) return resolve("");
      let done = false; const finish = (t) => { if (!done) { done = true; resolve(t || ""); } };
      try { window.turnstile.reset(tsId); window.turnstile.execute(tsId, { callback: finish }); } catch (e) { finish(""); }
      setTimeout(() => finish(window.turnstile && window.turnstile.getResponse ? window.turnstile.getResponse(tsId) : ""), 4000);
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = input.value.trim();
      if (!msg || busy) return;
      busy = true; input.value = "";
      addMsg(msg, "me");
      state.history.push({ role: "user", content: msg });
      const thinking = addMsg("…", "bot");
      try {
        const token = await getToken();
        const r = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: msg, history: state.history.slice(-8), turnstileToken: token }) });
        const data = await r.json();
        thinking.textContent = data.reply || "I'm sorry, I couldn't respond just now.";
        addCards(data.chapters);
        if (data.plan && data.plan.length) { state.plan = data.plan; addPlan(data.plan); }
        if (data.reply) state.history.push({ role: "assistant", content: data.reply });
        save(state);
      } catch (err) {
        thinking.textContent = "I couldn't reach the guide just now — please try again in a moment.";
      } finally { busy = false; input.focus(); }
    });
  }
  window.BMMGuide = { mount };
})();
