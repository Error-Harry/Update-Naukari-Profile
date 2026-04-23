/* Naukri Auto Update — vanilla SPA */

const TOKEN_KEY = "naukri_token";

const $ = (sel) => document.querySelector(sel);
const show = (el, on) => el.classList.toggle("hidden", !on);

function token() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

async function api(path, { method = "GET", body = null, form = null } = {}) {
  const headers = {};
  const t = token();
  if (t) headers["Authorization"] = "Bearer " + t;
  let payload = null;
  if (body !== null) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  } else if (form !== null) {
    payload = form;
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || detail; } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

function showBanner(kind, msg) {
  const el = $("#status-banner");
  const classes = {
    ok: "bg-emerald-50 border border-emerald-200 text-emerald-800",
    err: "bg-rose-50 border border-rose-200 text-rose-800",
    info: "bg-brand-50 border border-brand-100 text-brand-800",
  };
  el.className = "rounded-xl px-4 py-3 text-sm fade-in " + (classes[kind] || classes.info);
  el.textContent = msg;
  show(el, true);
  clearTimeout(showBanner._t);
  showBanner._t = setTimeout(() => show(el, false), 4000);
}

/* -------------------- auth screen -------------------- */

function switchTab(which) {
  $("#tab-login").classList.toggle("bg-white", which === "login");
  $("#tab-login").classList.toggle("shadow-sm", which === "login");
  $("#tab-login").classList.toggle("text-slate-500", which !== "login");
  $("#tab-register").classList.toggle("bg-white", which === "register");
  $("#tab-register").classList.toggle("shadow-sm", which === "register");
  $("#tab-register").classList.toggle("text-slate-500", which !== "register");
  show($("#form-login"), which === "login");
  show($("#form-register"), which === "register");
  show($("#auth-error"), false);
}

$("#tab-login").addEventListener("click", () => switchTab("login"));
$("#tab-register").addEventListener("click", () => switchTab("register"));

$("#form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const { access_token } = await api("/api/auth/login", {
      method: "POST",
      body: { email: fd.get("email"), password: fd.get("password") },
    });
    setToken(access_token);
    await enterApp();
  } catch (err) {
    $("#auth-error").textContent = err.message;
    show($("#auth-error"), true);
  }
});

$("#form-register").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/api/auth/register", {
      method: "POST",
      body: { name: fd.get("name"), email: fd.get("email"), password: fd.get("password") },
    });
    const { access_token } = await api("/api/auth/login", {
      method: "POST",
      body: { email: fd.get("email"), password: fd.get("password") },
    });
    setToken(access_token);
    await enterApp();
  } catch (err) {
    $("#auth-error").textContent = err.message;
    show($("#auth-error"), true);
  }
});

/* -------------------- app screen -------------------- */

$("#btn-logout").addEventListener("click", () => {
  clearToken();
  show($("#app-screen"), false);
  show($("#auth-screen"), true);
});

$("#in-schedule-mode").addEventListener("change", syncScheduleMode);
$("#in-enabled").addEventListener("change", () => {
  $("#lbl-enabled").textContent = $("#in-enabled").checked ? "Enabled" : "Disabled";
});

function syncScheduleMode() {
  const mode = $("#in-schedule-mode").value;
  show($("#time2-wrap"), mode === "twice");
}

function renderNav(user) {
  $("#nav-name").textContent = user.name;
  const badge = $("#nav-subscription");
  if (user.subscription === "paid") {
    badge.textContent = "Paid";
    badge.className = "text-xs px-3 py-1.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200";
  } else {
    badge.textContent = "Buy subscription";
    badge.className = "text-xs px-3 py-1.5 rounded-full font-medium bg-amber-50 text-amber-700 border border-amber-200 cursor-pointer";
    badge.onclick = () => showBanner("info", "Subscription flow coming soon.");
  }
}

function fmtDT(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function renderProfile(p) {
  $("#in-naukri-email").value = p?.naukri_email || "";
  $("#in-naukri-password").value = "";
  $("#in-schedule-mode").value = p?.schedule_mode || "once";
  $("#in-time1").value = (p?.schedule_time1 || "09:30").slice(0, 5);
  $("#in-time2").value = (p?.schedule_time2 || "13:45").slice(0, 5);
  $("#in-enabled").checked = p ? !!p.enabled : true;
  $("#lbl-enabled").textContent = $("#in-enabled").checked ? "Enabled" : "Disabled";
  $("#resume-current").textContent = p?.resume_filename ? `· current: ${p.resume_filename}` : "";
  syncScheduleMode();

  const info = [];
  if (p?.last_run_at) info.push(`Last run: ${fmtDT(p.last_run_at)} (${p.last_status})`);
  else info.push("No run yet.");
  if (p?.last_status === "failed" && p?.last_error) info.push(`Error: ${p.last_error}`);
  $("#last-run-info").textContent = info.join(" · ");
}

async function loadMe() {
  const me = await api("/api/me");
  renderNav(me.user);
  $("#in-name").value = me.user.name;
  renderProfile(me.profile);
}

async function loadRuns() {
  const rows = await api("/api/me/runs");
  const tbody = $("#runs-body");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="py-3 text-slate-400">No runs yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="py-2">${fmtDT(r.started_at)}</td>
      <td class="py-2">
        <span class="px-2 py-0.5 rounded text-xs font-medium ${
          r.status === "success" ? "bg-emerald-50 text-emerald-700" :
          r.status === "failed"  ? "bg-rose-50 text-rose-700" :
          "bg-slate-100 text-slate-700"
        }">${r.status}</span>
      </td>
      <td class="py-2">${r.attempts}</td>
      <td class="py-2 text-slate-500 max-w-xs truncate" title="${r.error || ''}">${r.error || "—"}</td>
    </tr>
  `).join("");
}

$("#btn-refresh-runs").addEventListener("click", () => loadRuns().catch(e => showBanner("err", e.message)));

$("#form-account").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { name: $("#in-name").value };
  const cur = $("#in-current-password").value;
  const neu = $("#in-new-password").value;
  if (neu) { body.current_password = cur; body.new_password = neu; }
  try {
    const user = await api("/api/me", { method: "PATCH", body });
    $("#in-current-password").value = "";
    $("#in-new-password").value = "";
    renderNav(user);
    showBanner("ok", "Account updated.");
  } catch (err) {
    showBanner("err", err.message);
  }
});

$("#form-profile").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData();
  if ($("#in-naukri-email").value) fd.append("naukri_email", $("#in-naukri-email").value);
  if ($("#in-naukri-password").value) fd.append("naukri_password", $("#in-naukri-password").value);
  fd.append("schedule_mode", $("#in-schedule-mode").value);
  fd.append("schedule_time1", $("#in-time1").value || "09:30");
  if ($("#in-schedule-mode").value === "twice") {
    fd.append("schedule_time2", $("#in-time2").value || "13:45");
  }
  fd.append("enabled", $("#in-enabled").checked ? "true" : "false");
  const file = $("#in-resume").files[0];
  if (file) fd.append("resume", file);
  try {
    const p = await api("/api/me/profile", { method: "PUT", form: fd });
    $("#in-naukri-password").value = "";
    $("#in-resume").value = "";
    renderProfile(p);
    showBanner("ok", "Profile saved and schedule updated.");
    loadRuns().catch(() => {});
  } catch (err) {
    showBanner("err", err.message);
  }
});

$("#btn-run-now").addEventListener("click", async () => {
  try {
    const res = await api("/api/me/run-now", { method: "POST" });
    showBanner("info", res.detail || "Run started.");
  } catch (err) {
    showBanner("err", err.message);
  }
});

/* -------------------- bootstrap -------------------- */

async function enterApp() {
  show($("#auth-screen"), false);
  show($("#app-screen"), true);
  try {
    await loadMe();
    await loadRuns();
  } catch (err) {
    clearToken();
    show($("#app-screen"), false);
    show($("#auth-screen"), true);
    showBanner("err", "Session expired. Please sign in again.");
  }
}

(async function init() {
  if (token()) {
    await enterApp();
  } else {
    switchTab("login");
    show($("#auth-screen"), true);
  }
})();
