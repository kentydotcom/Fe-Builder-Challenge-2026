(function () {

  const FE_KW = new Set([
    "pub","mut","uses","contract","struct","enum","trait","impl","where","fn",
    "let","if","else","return","match","loop","break","continue","for","while",
    "in","as","const","type","use","self","Self","init","recv","true","false",
    "and","or","not"
  ]);
  const FE_PRIM = new Set([
    "u8","u16","u32","u64","u128","u256","i8","i16","i32","i64","i128",
    "bool","Wei","Address","Ctx","Call","Log"
  ]);
  const SH_KW = new Set([
    "if","then","else","elif","fi","for","do","done","in","case","esac",
    "while","until","function","return","exit","echo","export","source",
    "local","set","unset","shift","read","printf","test","trap","wait",
    "cd","curl","bash","fe","foundryup"
  ]);
  const TOML_KW = new Set(["true","false"]);

  function escapeHtml(s) {
    return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  function langFromPath(path) {
    if (!path) return "plain";
    if (/\.fe$/.test(path)) return "fe";
    if (/\.(sh|bash)$/.test(path)) return "bash";
    if (/\.toml$/.test(path)) return "toml";
    if (/\.md$/.test(path)) return "md";
    return "plain";
  }

  function langFromBlock(pre, code) {
    if (pre.dataset.lang) return pre.dataset.lang;
    const cls = (code.className || "") + " " + (pre.className || "");
    const m = cls.match(/language-([a-z0-9+]+)/i);
    if (m) {
      const x = m[1].toLowerCase();
      if (x === "sh" || x === "shell" || x === "zsh") return "bash";
      if (x === "rust") return "fe";
      return x;
    }
    return "plain";
  }

  function pushTok(out, cls, text) {
    if (!text) return;
    out.push({ cls: cls || "", text });
  }

  function readIdent(s, i) {
    let j = i + 1;
    while (j < s.length && /[A-Za-z0-9_]/.test(s[j])) j++;
    return j;
  }

  function readString(s, i, quote) {
    let j = i + 1;
    while (j < s.length) {
      if (s[j] === "\\") { j += 2; continue; }
      if (s[j] === quote) return j + 1;
      if (s[j] === "\n" && quote !== "`") return j;
      j++;
    }
    return j;
  }

  function tokenizeFe(s) {
    const out = [];
    let i = 0;
    const n = s.length;
    while (i < n) {
      const c = s[i];
      if (c === "/" && s[i + 1] === "/") {
        let j = s.indexOf("\n", i);
        if (j < 0) j = n;
        pushTok(out, "comm", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === "/" && s[i + 1] === "*") {
        let j = s.indexOf("*/", i + 2);
        j = j < 0 ? n : j + 2;
        pushTok(out, "comm", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === "#" && s[i + 1] === "[") {
        let j = i + 2;
        let depth = 1;
        while (j < n && depth > 0) {
          if (s[j] === '"' || s[j] === "'") { j = readString(s, j, s[j]); continue; }
          if (s[j] === "[") depth++;
          else if (s[j] === "]") depth--;
          j++;
        }
        pushTok(out, "attr", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === '"' || c === "'") {
        const j = readString(s, i, c);
        pushTok(out, "str", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === "0" && (s[i + 1] === "x" || s[i + 1] === "X") && /[0-9a-fA-F]/.test(s[i + 2] || "")) {
        let j = i + 2;
        while (j < n && /[0-9a-fA-F_]/.test(s[j])) j++;
        pushTok(out, "num", s.slice(i, j));
        i = j;
        continue;
      }
      if (/[0-9]/.test(c)) {
        let j = i + 1;
        while (j < n && /[0-9_]/.test(s[j])) j++;
        pushTok(out, "num", s.slice(i, j));
        i = j;
        continue;
      }
      if (/[A-Za-z_]/.test(c)) {
        const j = readIdent(s, i);
        const id = s.slice(i, j);
        if (FE_KW.has(id)) pushTok(out, "kw", id);
        else if (FE_PRIM.has(id) || /^[A-Z]/.test(id)) pushTok(out, "type", id);
        else if (s[j] === "(") pushTok(out, "fn", id);
        else pushTok(out, "", id);
        i = j;
        continue;
      }
      if ("{}[]().,;:".includes(c) || (c === "-" && s[i + 1] === ">")) {
        if (c === "-" && s[i + 1] === ">") {
          pushTok(out, "punct", "->");
          i += 2;
          continue;
        }
        pushTok(out, "punct", c);
        i++;
        continue;
      }
      pushTok(out, "", c);
      i++;
    }
    return out;
  }

  function tokenizeBash(s) {
    const out = [];
    let i = 0;
    const n = s.length;
    while (i < n) {
      const c = s[i];
      if (c === "#" && (i === 0 || /\s/.test(s[i - 1]))) {
        let j = s.indexOf("\n", i);
        if (j < 0) j = n;
        pushTok(out, "comm", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === '"' || c === "'" || c === "`") {
        const j = readString(s, i, c);
        pushTok(out, "str", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === "$") {
        let j = i + 1;
        if (s[j] === "{") {
          j = s.indexOf("}", j);
          j = j < 0 ? n : j + 1;
        } else {
          while (j < n && /[A-Za-z0-9_@*#?-]/.test(s[j])) j++;
          if (j === i + 1) j++;
        }
        pushTok(out, "var", s.slice(i, j));
        i = j;
        continue;
      }
      if (/[A-Za-z_.]/.test(c)) {
        const j = readIdent(s, i);
        const id = s.slice(i, j);
        if (SH_KW.has(id)) pushTok(out, "kw", id);
        else if (s[j] === "(" || (i === 0 || s[i - 1] === "\n" || s[i - 1] === " " || s[i - 1] === "|")) {
          // first word on a line looks like a command
          const atStart = i === 0 || s[i - 1] === "\n" || /[|;(&\s]/.test(s[i - 1]);
          const prevTok = i > 0 && s.slice(Math.max(0, i - 2), i).trim();
          if (atStart) pushTok(out, "fn", id);
          else pushTok(out, "", id);
        } else pushTok(out, "", id);
        i = j;
        continue;
      }
      if (c === "-" && /[A-Za-z0-9]/.test(s[i + 1] || "")) {
        let j = i + 1;
        while (j < n && /[A-Za-z0-9_=-]/.test(s[j])) j++;
        pushTok(out, "attr", s.slice(i, j));
        i = j;
        continue;
      }
      pushTok(out, "", c);
      i++;
    }
    return out;
  }

  function tokenizeToml(s) {
    const out = [];
    let i = 0;
    const n = s.length;
    while (i < n) {
      const c = s[i];
      if (c === "#") {
        let j = s.indexOf("\n", i);
        if (j < 0) j = n;
        pushTok(out, "comm", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === '"' || c === "'") {
        const j = readString(s, i, c);
        pushTok(out, "str", s.slice(i, j));
        i = j;
        continue;
      }
      if (c === "[") {
        let j = s.indexOf("]", i);
        j = j < 0 ? n : j + 1;
        pushTok(out, "type", s.slice(i, j));
        i = j;
        continue;
      }
      if (/[A-Za-z_]/.test(c)) {
        const j = readIdent(s, i);
        const id = s.slice(i, j);
        if (TOML_KW.has(id)) pushTok(out, "kw", id);
        else pushTok(out, "fn", id);
        i = j;
        continue;
      }
      if (/[0-9]/.test(c)) {
        let j = i + 1;
        while (j < n && /[0-9_.]/.test(s[j])) j++;
        pushTok(out, "num", s.slice(i, j));
        i = j;
        continue;
      }
      pushTok(out, "", c);
      i++;
    }
    return out;
  }

  function tokenizeMd(s) {
    const out = [];
    const lines = s.split("\n");
    lines.forEach((line, idx) => {
      if (/^\s*#/.test(line)) pushTok(out, "head", line);
      else if (/^\s*```/.test(line)) pushTok(out, "attr", line);
      else if (/^\s*>/.test(line)) pushTok(out, "comm", line);
      else if (/^\s*([-*] |\d+\. )/.test(line)) {
        const m = line.match(/^(\s*(?:[-*] |\d+\. ))(.*)$/);
        pushTok(out, "kw", m[1]);
        pushTok(out, "", m[2]);
      } else {
        // inline `code`
        let i = 0;
        while (i < line.length) {
          if (line[i] === "`") {
            let j = line.indexOf("`", i + 1);
            if (j < 0) { pushTok(out, "", line.slice(i)); break; }
            pushTok(out, "str", line.slice(i, j + 1));
            i = j + 1;
            continue;
          }
          let j = line.indexOf("`", i);
          if (j < 0) { pushTok(out, "", line.slice(i)); break; }
          pushTok(out, "", line.slice(i, j));
          i = j;
        }
      }
      if (idx < lines.length - 1) pushTok(out, "", "\n");
    });
    return out;
  }

  function tokenize(text, lang) {
    if (lang === "fe") return tokenizeFe(text);
    if (lang === "bash") return tokenizeBash(text);
    if (lang === "toml") return tokenizeToml(text);
    if (lang === "md" || lang === "markdown") return tokenizeMd(text);
    return [{ cls: "", text }];
  }

  function renderHighlighted(text, lang, start) {
    const tokens = tokenize(text, lang || "plain");
    const lines = [[]];
    tokens.forEach((tok) => {
      const parts = tok.text.split("\n");
      parts.forEach((part, i) => {
        if (i > 0) lines.push([]);
        if (part) lines[lines.length - 1].push({ cls: tok.cls, text: part });
      });
    });
    const startAt = Number(start) > 0 ? Number(start) : 1;
    const width = String(startAt + lines.length - 1).length;
    return lines
      .map((segs, i) => {
        const n = String(startAt + i).padStart(width, " ");
        const inner = segs
          .map((s) =>
            s.cls
              ? '<span class="tok-' + s.cls + '">' + escapeHtml(s.text) + "</span>"
              : escapeHtml(s.text)
          )
          .join("");
        return '<span class="ln">' + n + "</span>" + inner;
      })
      .join("\n");
  }

  function paintPre(pre) {
    const code = pre.querySelector("code") || pre;
    if (pre.dataset.highlighted === "1") return;
    const text = code.textContent;
    const lang = langFromBlock(pre, code);
    const start = pre.getAttribute("data-start") || "1";
    code.innerHTML = renderHighlighted(text, lang, start);
    pre.dataset.highlighted = "1";
  }

  function paintStaticCode() {
    document.querySelectorAll(".excerpt pre, .walkthrough pre").forEach(paintPre);
  }

  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));

  function panelId(name) {
    return "panel-" + name;
  }

  function showTab(name, opts) {
    const known = tabs.some((t) => t.dataset.tab === name);
    if (!known) name = "overview";
    tabs.forEach((tab) => {
      const on = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    panels.forEach((panel) => {
      const on = panel.id === panelId(name);
      panel.classList.toggle("active", on);
      if (on) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
    if (!opts || !opts.skipHash) {
      const hash = location.hash || "";
      if (name === "source" && hash.indexOf("#source/") === 0) {
        /* keep file hash */
      } else if (location.hash !== "#" + name) {
        history.replaceState(null, "", "#" + name);
      }
    }
    if (opts && opts.scrollTop) {
      window.scrollTo(0, 0);
    }
    if (name === "source" && typeof window.loadSourceFile === "function") {
      const code = document.getElementById("source-code");
      const empty = !code || !code.textContent;
      const list = window.SOURCE_FILES || [];
      if (empty && list.length) window.loadSourceFile(list[0], { skipHash: true });
    }
  }

  function parseHash() {
    const raw = (location.hash || "#overview").slice(1);
    if (raw.indexOf("source/") === 0) {
      const file = decodeURIComponent(raw.slice("source/".length));
      showTab("source", { skipHash: true });
      if (file && window.loadSourceFile) window.loadSourceFile(file, { skipHash: true });
      return;
    }
    showTab(raw || "overview");
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => {
      showTab(tab.dataset.tab, { scrollTop: true });
    });
    tab.addEventListener("keydown", (e) => {
      const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!dir) return;
      e.preventDefault();
      const next = tabs[(i + dir + tabs.length) % tabs.length];
      next.focus();
      showTab(next.dataset.tab, { scrollTop: true });
    });
  });

  window.addEventListener("hashchange", parseHash);

  /* Source browser */
  const list = document.getElementById("source-list");
  const viewPath = document.getElementById("source-path");
  const viewMeta = document.getElementById("source-meta");
  const viewCode = document.getElementById("source-code");
  const files = window.SOURCE_FILES || [];

  function renderCode(text, path) {
    return renderHighlighted(text.replace(/\n$/, ""), langFromPath(path), 1);
  }

  async function loadSourceFile(path, opts) {
    const btns = list ? list.querySelectorAll("button[data-path]") : [];
    btns.forEach((b) => b.setAttribute("aria-current", b.dataset.path === path ? "true" : "false"));
    if (viewPath) viewPath.textContent = path;
    if (viewMeta) viewMeta.textContent = "loading…";
    if (viewCode) viewCode.textContent = "";
    try {
      const res = await fetch("tree/" + path);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const text = await res.text();
      const lines = text.replace(/\n$/, "").split("\n").length;
      if (viewMeta) viewMeta.textContent = lines + " lines";
      if (viewCode) viewCode.innerHTML = renderCode(text, path);
      if (!opts || !opts.skipHash) {
        history.replaceState(null, "", "#source/" + encodeURIComponent(path).replace(/%2F/g, "/"));
      }
    } catch (err) {
      if (viewMeta) viewMeta.textContent = "could not load";
      if (viewCode) viewCode.textContent = String(err);
    }
  }

  window.loadSourceFile = loadSourceFile;

  if (list) {
    list.querySelectorAll("button[data-path]").forEach((btn) => {
      btn.addEventListener("click", () => loadSourceFile(btn.dataset.path));
    });
  }

  document.querySelectorAll("[data-open-source]").forEach((a) => {
    a.addEventListener("click", (e) => {
      const path = a.getAttribute("data-open-source");
      if (!path) return;
      e.preventDefault();
      showTab("source");
      loadSourceFile(path);
      const panel = document.getElementById("panel-source");
      if (panel) panel.scrollIntoView({ block: "start" });
    });
  });

  paintStaticCode();
  parseHash();
  if (!location.hash || location.hash === "#") {
    showTab("overview");
  }
  if ((!location.hash || location.hash === "#overview" || location.hash === "#source") && files.length && !location.hash.startsWith("#source/")) {
    if (location.hash === "#source" || (document.getElementById("panel-source") || {}).classList?.contains("active")) {
      loadSourceFile(files[0], { skipHash: true });
    }
  }
  if (location.hash === "#source" && files.length) {
    loadSourceFile(files[0], { skipHash: true });
  }
})();

(function () {
  const deck = document.getElementById("stage-deck");
  if (!deck) return;
  const logEl = document.getElementById("stage-log");
  const metaEl = document.getElementById("stage-meta");
  const consoleEl = document.getElementById("stage-console");
  let cache = null;

  async function loadLogs() {
    if (cache) return cache;
    const res = await fetch("assets/runs/e2e-20261124.json");
    if (!res.ok) throw new Error("HTTP " + res.status);
    cache = await res.json();
    return cache;
  }

  function show(title, text) {
    if (!consoleEl || !logEl || !metaEl) return;
    consoleEl.hidden = false;
    metaEl.textContent = title;
    logEl.textContent = text;
    consoleEl.scrollIntoView({ block: "nearest" });
  }

  function fail(err) {
    show("Could not load recorded logs", String(err));
  }

  deck.querySelectorAll("[data-stage]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const data = await loadLogs();
        const st = (data.stages || []).find((s) => String(s.n) === btn.dataset.stage);
        if (!st) throw new Error("unknown stage");
        show("Stage " + st.n + " · " + st.id + " — " + st.title, String(st.log || "").replace(/\n$/, ""));
      } catch (err) {
        fail(err);
      }
    });
  });

  const all = deck.querySelector("[data-run-all]");
  if (all) {
    all.addEventListener("click", async () => {
      try {
        const data = await loadLogs();
        const body = (data.stages || [])
          .map((s) => "======== " + s.n + " " + s.id + " — " + s.title + " ========\n" + String(s.log || "").trimEnd())
          .join("\n\n");
        show("Recorded --ci run · 24 Nov 2026", body + "\n\n" + (data.result || "PASS  8 stages, 0 failed") + "\n");
      } catch (err) {
        fail(err);
      }
    });
  }

  deck.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cmd = btn.getAttribute("data-copy") || "";
      try {
        await navigator.clipboard.writeText(cmd);
        const prev = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = prev; }, 1200);
      } catch (_) {
        const prev = btn.textContent;
        btn.textContent = "Copy failed";
        setTimeout(() => { btn.textContent = prev; }, 1200);
      }
    });
  });
})();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}
