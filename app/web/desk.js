// [K] Desk view: polls /api/desk, emergencies first. A new emergency flashes and (if enabled) beeps until acknowledged.
"use strict";

const LANG = { hi: "हिन्दी", bn: "বাংলা", en: "English" };
let soundOn = false, seen = new Set(), audioCtx = null;

function beep() {
  if (!soundOn) return;
  audioCtx = audioCtx || new AudioContext();
  const o = audioCtx.createOscillator(), g = audioCtx.createGain();
  o.frequency.value = 880; g.gain.value = 0.15; o.connect(g).connect(audioCtx.destination);
  o.start(); o.stop(audioCtx.currentTime + 0.35);
}

function ago(t, now) {
  const s = Math.max(0, Math.round(now - t));
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)} min ago`;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

async function refresh() {
  let data;
  try { data = await (await fetch("/api/desk")).json(); } catch { return; }
  const list = document.getElementById("list");
  if (!data.sessions.length) return;
  list.replaceChildren();
  let alarm = false;
  for (const p of data.sessions) {
    const card = el("article", `pt ${p.level || ""}`);
    const isNew = p.level === "emergency" && !p.acknowledged;
    if (isNew) { card.classList.add("new"); if (!seen.has(p.session_id)) alarm = true; }
    if (p.level === "emergency") seen.add(p.session_id);
    const top = el("div", "row");
    top.append(el("span", "who", `${p.speaker === "caregiver" ? "Caregiver for patient" : "Patient"} · ${LANG[p.lang] || p.lang || ""}`),
               el("span", "meta", `${p.session_id.slice(0, 8)} · turn ${p.turns} · ${p.phase || ""} · ${ago(p.updated, data.now)}`));
    card.append(top);
    if (p.level) {
      const ids = p.red_flags.map((f) => f.id).join(", ");
      card.append(el("div", "flag", `${p.level === "emergency" ? "EMERGENCY" : "Urgent"}: ${ids}`));
      if (p.escalation && p.escalation.reason_clinician) card.append(el("div", "sum", p.escalation.reason_clinician));
    }
    card.append(el("div", "complaint", p.complaint ? `“${p.complaint}”` : "(no complaint yet)"));
    if (p.summary) card.append(el("div", "sum", p.summary));
    if (isNew) {
      const b = el("button", "", "Seen, going now");
      b.onclick = async () => { await fetch(`/api/desk/${encodeURIComponent(p.session_id)}/ack`, { method: "POST" }); refresh(); };
      card.append(b);
    }
    list.append(card);
  }
  if (alarm) beep();
}

document.getElementById("sound").onclick = (e) => {
  soundOn = !soundOn;
  e.target.setAttribute("aria-pressed", String(soundOn));
  e.target.textContent = soundOn ? "🔔 Sound on" : "🔕 Sound off";
  if (soundOn) beep();
};
refresh();
setInterval(refresh, 2000);
