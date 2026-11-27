// [K] K3 voice app. Speech in: Wispr Flow via /api/stt when the server has a key (we record, detect the end of
// speech, upload), else the browser's Web Speech API. Speech out: browser speechSynthesis until K2 picks a TTS engine.
// Neither choice touches the C1 contract.
"use strict";

const CONTRACT = "1.0";
const BCP47 = { hi: "hi-IN", bn: "bn-IN", en: "en-IN" };
const UI = {
  hi: { ready: "बोलने के लिए माइक दबाएँ", listening: "सुन रहे हैं…", thinking: "सोच रहे हैं…", speaking: "बोल रहे हैं…", done: "बातचीत पूरी हुई", offline: "माफ़ कीजिए, अभी जुड़ नहीं पा रहे। फिर से बोलिए।" },
  bn: { ready: "কথা বলতে মাইক চাপুন", listening: "শুনছি…", thinking: "ভাবছি…", speaking: "বলছি…", done: "কথা শেষ হয়েছে", offline: "মাফ করবেন, এখন সংযোগ হচ্ছে না। আবার বলুন।" },
  en: { ready: "Tap the mic to speak", listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…", done: "Conversation finished", offline: "Sorry, I can't connect right now. Please say that again." },
};
const FIELD_LABEL = { chief_complaint: "Complaint", duration: "Since", age: "Age", conditions: "Conditions", medicines: "Medicines" };

const $ = (id) => document.getElementById(id);
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

let lang = "hi", sessionId = null, turnNo = 0, agentState = null, lastResp = null;
let busy = false, rec = null, recognising = false, speaking = false, currentSay = null;
let tSpeechEnd = 0, tThinkTimer = null, autoListen = true, aborted = false;
let sttMode = "browser", micStream = null, mediaRec = null;
const VAD = { threshold: 0.018, startMs: 150, silenceMs: 1200, silenceLongMs: 1800, noSpeechMs: 8000, maxMs: 30000 };

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
  const pt = st.patient || {};
  if (pt.age_years || pt.age_band) rows.push(["age", pt.age_years ? String(pt.age_years) : pt.age_band, "heard"]);
  if (c && c.value && c.value.length) rows.push(["conditions", c.value.join(", "), c.status]);
  const m = st.history && st.history.medicines_taken;
  if (m && m.value && m.value.length) rows.push(["medicines", m.value.join(", "), m.status]);
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
  const e = r.escalation;
  if (!e) return;
  const box = $("escalation"), prevEmergency = box.classList.contains("emergency") && !box.hidden;
  if (prevEmergency && e.level !== "emergency") return;  // never downgrade a shown emergency within the session
  box.hidden = false;
  box.classList.toggle("emergency", e.level === "emergency");
  box.classList.toggle("urgent", e.level !== "emergency");
  $("esc-text").textContent = e.message;
  const call = e.call;
  // Urgent ("see a doctor today") has no number: show no call button rather than a misleading 112.
  $("esc-call").hidden = !call;
  if (call) { $("esc-call").href = `tel:${call.number}`; $("esc-call").querySelector("span").textContent = `${call.number} · ${call.label}`; }
  // A helpline (e.g. Tele-MANAS 14416 for self-harm) is primary, and 112 stays one tap away as a second button.
  $("esc-call2").hidden = !call || call.number === "112";
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
  bubble("agent", r.say.text, r.action !== "escalate" ? "" : (r.escalation && r.escalation.level === "urgent" ? "urgent" : "escalate"));
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
  if (sttMode === "wispr") return listenWispr();
  return listenBrowser();
}

// Wispr path: record with echo cancellation, end the turn after a pause, upload, then send the transcript to the agent.
async function listenWispr() {
  if (recognising || busy) return;
  try {
    micStream = micStream || await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  } catch {
    status("ready", "Microphone blocked: allow it in the browser, or type below."); autoListen = false; return;
  }
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const an = ctx.createAnalyser(); an.fftSize = 1024;
  ctx.createMediaStreamSource(micStream).connect(an);
  const buf = new Float32Array(an.fftSize);
  const chunks = [];
  const r = new MediaRecorder(micStream);
  mediaRec = r; aborted = false; recognising = true; tSpeechEnd = 0;
  const silenceMs = lastResp && lastResp.expect && lastResp.expect.patience === "long" ? VAD.silenceLongMs : VAD.silenceMs;
  const t0 = performance.now();
  let loud = 0, spoke = false, lastVoice = 0, raf = 0;
  r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const tick = () => {
    an.getFloatTimeDomainData(buf);
    let sum = 0; for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length), now = performance.now();
    if (rms > VAD.threshold) { loud += 16; if (loud >= VAD.startMs) { spoke = true; lastVoice = now; } } else loud = 0;
    $("live").textContent = spoke ? "●".repeat(Math.min(12, Math.round(rms * 300))) : "";
    const done = (spoke && now - lastVoice > silenceMs) || (!spoke && now - t0 > VAD.noSpeechMs) || now - t0 > VAD.maxMs;
    if (done && r.state === "recording") { tSpeechEnd = spoke ? lastVoice : now; r.stop(); return; }
    raf = requestAnimationFrame(tick);
  };
  r.onstart = () => { status("listening"); raf = requestAnimationFrame(tick); };
  r.onstop = async () => {
    cancelAnimationFrame(raf); ctx.close(); recognising = false; mediaRec = null; $("live").textContent = "";
    if (aborted) return;
    if (!spoke) { if (!busy) send("no_speech"); return; }
    if (!tSpeechEnd) tSpeechEnd = performance.now();
    const blob = new Blob(chunks, { type: r.mimeType || "audio/webm" });
    status("thinking");
    const prompt = (lastResp && lastResp.say && lastResp.say.text) || "";
    let out;
    try {
      const res = await fetch(`/api/stt?lang=${lang}&prompt=${encodeURIComponent(prompt)}`, { method: "POST", body: blob, signal: AbortSignal.timeout(12000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      out = await res.json();
    } catch (e) { // Wispr unavailable: switch to browser recognition for the rest of the session
      sttMode = "browser"; $("meta").textContent = "Wispr unavailable, using browser speech recognition";
      return listenBrowser();
    }
    const text = (out.text || "").trim();
    if (!text) { send("no_speech"); return; }
    bubble("user", text, "", "🎤");
    const d = detect(text);
    send("utterance", { text, language: ["hi", "bn", "en"].includes(out.language) ? out.language : d.language,
                        mixed_with: d.mixed_with, language_confidence: null, stt_confidence: null, alternatives: [],
                        stt_engine: out.engine || "wispr" },
         { duration_ms: out.duration_ms ?? Math.round(performance.now() - t0), truncated: performance.now() - t0 > VAD.maxMs });
    $("meta").textContent = `wispr ${out.latency_ms} ms`;
  };
  r.start(250);
}

function stopCapture(abort) {
  if (abort) aborted = true;
  if (mediaRec && mediaRec.state === "recording") mediaRec.stop();
  else if (rec && recognising) (abort ? rec.abort() : rec.stop());
}

function listenBrowser() {
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
  if (recognising) { stopCapture(false); return; }
  autoListen = true;
  listen();
});
$("typed").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("typed-in").value.trim();
  if (!text || busy) return;
  if (!sessionId) { restart(text); return; }
  $("typed-in").value = "";
  if (recognising) stopCapture(true);
  speechSynthesis.cancel();
  tSpeechEnd = performance.now();
  bubble("user", text, "", "⌨");
  const d = detect(text);
  send("utterance", { text, language: d.language, mixed_with: d.mixed_with, language_confidence: null,
                      stt_confidence: null, alternatives: [], stt_engine: "typed" }, null);
});
$("restart").addEventListener("click", () => restart());

async function restart(firstTyped) {
  if (recognising) stopCapture(true);
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
fetch("/v1/health").then((r) => r.json()).then((h) => {
  sttMode = h.stt === "wispr" && window.MediaRecorder ? "wispr" : "browser";
  $("meta").textContent = `speech-to-text: ${sttMode === "wispr" ? "Wispr Flow" : "browser"} · agent: ${h.agent}`;
  const notes = [];
  if ((h.keys_missing || []).includes("WISPR_API_KEY")) notes.push("Wispr key not set: using the browser's speech recognition.");
  if ((h.keys_missing || []).includes("GEMINI_API_KEY")) notes.push("Gemini key not set: the agent runs on its safety rules only.");
  if (notes.length) { $("keys").textContent = notes.join(" "); $("keys").hidden = false; }
}).catch(() => {});
