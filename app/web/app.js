// [K] K3 voice app. Speech in/out uses the browser (Web Speech API) for now; K2 picks the real STT/TTS engines,
// which will plug in behind listen()/speak() without changing the C1 contract.
"use strict";

const CONTRACT = "1.0";
const BCP47 = { hi: "hi-IN", bn: "bn-IN", en: "en-IN" };
const UI = {
  hi: { ready: "बोलने के लिए माइक दबाएँ", listening: "सुन रहे हैं…", thinking: "सोच रहे हैं…", speaking: "बोल रहे हैं…", done: "बातचीत पूरी हुई", offline: "माफ़ कीजिए, अभी जुड़ नहीं पा रहे। फिर से बोलिए।" },
  bn: { ready: "কথা বলতে মাইক চাপুন", listening: "শুনছি…", thinking: "ভাবছি…", speaking: "বলছি…", done: "কথা শেষ হয়েছে", offline: "মাফ করবেন, এখন সংযোগ হচ্ছে না। আবার বলুন।" },
  en: { ready: "Tap the mic to speak", listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…", done: "Conversation finished", offline: "Sorry, I can't connect right now. Please say that again." },
};
const FIELD_LABEL = { chief_complaint: "Complaint", duration: "Since", conditions: "Conditions" };

const $ = (id) => document.getElementById(id);
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

let lang = "hi", sessionId = null, turnNo = 0, agentState = null, lastResp = null;
let busy = false, rec = null, recognising = false, speaking = false, currentSay = null;
let tSpeechEnd = 0, tThinkTimer = null, autoListen = true, aborted = false;

// ---------- language ----------
function setLang(l) {
  lang = l;
  document.querySelectorAll(".langs button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.lang === l)));
  document.documentElement.lang = l;
  status("ready");
}
document.querySelectorAll(".langs button").forEach((b) => b.addEventListener("click", () => {
  setLang(b.dataset.lang);
  if (turnNo === 0 || (lastResp && lastResp.action === "done")) restart();
}));

// Script-based language guess for the transcript. Browser STT is locked to the chosen language, so this mostly
// catches code-mixing (Latin words inside Devanagari/Bengali, or romanised Hindi/Bengali).
function detect(text) {
  const deva = (text.match(/[ऀ-ॿ]/g) || []).length;
  const beng = (text.match(/[ঀ-৿]/g) || []).length;
  const latin = (text.match(/[A-Za-z]/g) || []).length;
  const indic = deva >= beng ? ["hi", deva] : ["bn", beng];
  if (indic[1] === 0) return { language: lang, mixed_with: lang === "en" ? [] : ["en"] };
  return { language: indic[0], mixed_with: latin > 2 ? ["en"] : [] };
}

// ---------- UI helpers ----------
function status(key, extra) {
  $("status").textContent = extra || (UI[lang][key] ?? key);
  const mic = $("mic");
  mic.classList.toggle("listening", key === "listening");
  mic.classList.toggle("thinking", key === "thinking");
  mic.classList.toggle("speaking", key === "speaking");
}
function bubble(who, text, cls = "", tag = "") {
  $("empty").hidden = true;
  const d = document.createElement("div");
  d.className = `msg ${who} ${cls}`.trim();
  d.textContent = text;
  if (tag) { const t = document.createElement("span"); t.className = "tag"; t.textContent = tag; d.append(t); }
  $("chat").append(d);
  d.scrollIntoView({ behavior: "smooth", block: "end" });
  return d;
}
function renderSummary(r) {
  const st = r.state || {};
  const rows = [];
  if (st.chief_complaint && st.chief_complaint.said) rows.push(["chief_complaint", st.chief_complaint.said, st.chief_complaint.status]);
  const s0 = (st.symptoms || [])[0];
  if (s0 && s0.duration) rows.push(["duration", s0.duration, s0.status]);
  const c = st.history && st.history.conditions;
  if (c && c.value && c.value.length) rows.push(["conditions", c.value.join(", "), c.status]);
  const dl = $("fields"); dl.replaceChildren();
  for (const [k, v, s] of rows) {
    const dt = document.createElement("dt"); dt.textContent = FIELD_LABEL[k] || k;
    const dd = document.createElement("dd"); dd.textContent = v;
    const b = document.createElement("span"); b.className = `st ${s}`; b.textContent = s; dd.append(b);
    dl.append(dt, dd);
  }
  $("summary").hidden = rows.length === 0;
  const clin = r.display && r.display.summary_clinician;
  $("clin").hidden = !clin; $("clin-text").textContent = clin || "";
}
function renderEscalation(r) {
  if (!r.escalation) return;
  $("escalation").hidden = false;
  $("esc-text").textContent = r.escalation.message;
  const call = r.escalation.call;
  if (call) { $("esc-call").href = `tel:${call.number}`; $("esc-call").querySelector("span").textContent = `${call.number} · ${call.label}`; }
}

// ---------- contract calls ----------
async function send(event, transcript = null, audio = null) {
  if (busy) return;
  busy = true;
  const req = { contract: CONTRACT, session_id: sessionId, turn: turnNo, event, transcript, audio,
                state: agentState, ui_lang_hint: lang, client: { app: "k3-web", version: "0.1" } };
  clearTimeout(tThinkTimer);
  tThinkTimer = setTimeout(() => status("thinking"), 1200); // never look frozen (C1 review, Q4)
  const t0 = performance.now();
  let r;
  try {
    const res = await fetch("/v1/turn", { method: "POST", headers: { "Content-Type": "application/json" },
                                          body: JSON.stringify(req), signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    r = await res.json();
  } catch (e) {
    // Contract §9: agent unreachable -> our own canned line, keep the last state, nothing lost.
    clearTimeout(tThinkTimer); busy = false;
    bubble("agent", UI[lang].offline, "", "offline");
    speak({ text: UI[lang].offline, language: lang, pace: "normal", interruptible: true }, () => listen());
    return;
  }
  clearTimeout(tThinkTimer);
  busy = false;
  turnNo += 1;
  agentState = r.state; lastResp = r;
  const roundtrip = Math.round(performance.now() - t0);
  bubble("agent", r.say.text, r.action === "escalate" ? "escalate" : "");
  renderSummary(r); renderEscalation(r);
  $("meta").textContent = `agent ${r.debug?.model || ""} · round trip ${roundtrip} ms`;
  const next = r.action === "done" ? () => status("done") : () => { if (autoListen) listen(); else status("ready"); };
  speak(r.say, next, event === "utterance" ? tSpeechEnd : 0);
}

// ---------- speech out ----------
function pickVoice(l) {
  const vs = speechSynthesis.getVoices();
  return vs.find((v) => v.lang === BCP47[l]) || vs.find((v) => v.lang.startsWith(l)) || null;
}
function speak(say, onEnd, tEnd = 0) {
  currentSay = say;
  if (!("speechSynthesis" in window)) { onEnd && onEnd(); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(say.text);
  u.lang = BCP47[say.language] || BCP47[lang];
  const v = pickVoice(say.language);
  if (v) u.voice = v;
  u.rate = say.pace === "slow" ? 0.8 : 0.95;
  u.onstart = () => {
    speaking = true; status("speaking");
    if (tEnd) { // K's headline number: end of user speech -> reply audio starts
      const ms = Math.round(performance.now() - tEnd);
      $("meta").textContent += ` · speech-end→voice ${ms} ms`;
      fetch("/api/metrics", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, turn: turnNo, end_to_voice_ms: ms, lang, voice: v ? v.name : null }) }).catch(() => {});
    }
  };
  u.onend = u.onerror = () => { speaking = false; currentSay = null; onEnd && onEnd(); };
  if (!v) $("meta").textContent += ` · no ${say.language} voice on this device: captions only`;
  speechSynthesis.speak(u);
}

// ---------- speech in ----------
function listen() {
  if (!SR) { status("ready", "Speech recognition isn't available in this browser. Type below, or use Chrome."); return; }
  if (recognising || busy) return;
  rec = new SR();
  const thisRec = rec;
  aborted = false;
  rec.lang = BCP47[lang];
  rec.interimResults = true;
  rec.maxAlternatives = 3;
  rec.continuous = false;
  let interim = null, finalText = "", conf = null, alts = [], tStart = performance.now(), got = false;
  rec.onstart = () => { recognising = true; status("listening"); };
  rec.onresult = (e) => {
    let txt = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      if (res.isFinal) {
        finalText += res[0].transcript; conf = res[0].confidence || null;
        alts = Array.from(res).slice(1).map((a) => a.transcript).filter(Boolean);
      } else txt += res[0].transcript;
    }
    $("live").textContent = (finalText + txt).trim();
  };
  rec.onspeechend = () => { tSpeechEnd = performance.now(); };
  let err = null;
  rec.onerror = (e) => {
    err = e.error;
    if (e.error === "not-allowed" || e.error === "service-not-allowed") status("ready", "Microphone blocked: allow it in the browser, or type below.");
    else if (e.error === "audio-capture") status("ready", "No microphone found. Type below instead.");
    else if (e.error === "network") status("ready", "Speech recognition needs a connection. Type below, or try again.");
  };
  rec.onend = () => {
    recognising = false; $("live").textContent = "";
    if (!tSpeechEnd) tSpeechEnd = performance.now();
    const text = finalText.trim();
    if (rec !== thisRec || aborted) return;              // superseded (typed input, restart, barge-in)
    if (!text) {
      // Only real silence counts as no_speech. A mic/permission/network failure is not the patient being quiet.
      if ((err === null || err === "no-speech") && !busy) send("no_speech");
      else if (err !== null && err !== "aborted" && err !== "no-speech") autoListen = false;
      return;
    }
    got = true;
    bubble("user", text, "", "🎤");
    const d = detect(text);
    send("utterance", { text, language: d.language, mixed_with: d.mixed_with, language_confidence: null,
                        stt_confidence: conf, alternatives: alts, stt_engine: "webspeech" },
         { duration_ms: Math.round(performance.now() - tStart), truncated: false });
  };
  tSpeechEnd = 0;
  try { rec.start(); } catch { recognising = false; }
}

// ---------- controls ----------
$("mic").addEventListener("click", () => {
  if (!sessionId) return restart();
  if (speaking) { // barge-in: stop the agent unless it is an escalation (interruptible: false)
    if (currentSay && currentSay.interruptible === false) return;
    speechSynthesis.cancel(); speaking = false; listen(); return;
  }
  if (recognising) { rec.stop(); return; }
  autoListen = true;
  listen();
});
$("typed").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("typed-in").value.trim();
  if (!text || busy) return;
  if (!sessionId) { restart(text); return; }
  $("typed-in").value = "";
  if (recognising) { aborted = true; rec.abort(); }
  speechSynthesis.cancel();
  tSpeechEnd = performance.now();
  bubble("user", text, "", "⌨");
  const d = detect(text);
  send("utterance", { text, language: d.language, mixed_with: d.mixed_with, language_confidence: null,
                      stt_confidence: null, alternatives: [], stt_engine: "typed" }, null);
});
$("restart").addEventListener("click", () => restart());

async function restart(firstTyped) {
  if (rec && recognising) { aborted = true; rec.abort(); }
  autoListen = true;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  sessionId = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
  turnNo = 0; agentState = null; lastResp = null; busy = false;
  $("chat").replaceChildren($("empty")); $("empty").hidden = false;
  $("summary").hidden = true; $("escalation").hidden = true; $("meta").textContent = "";
  await send("start");
  if (firstTyped) { $("typed-in").value = firstTyped; $("typed").requestSubmit(); }
}

if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};
setLang("hi");
