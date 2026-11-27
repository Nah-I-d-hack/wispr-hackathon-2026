// [K] Browser "phone call" to Bolo. The mic streams 20 ms PCM16 16 kHz frames over a WebSocket; the server decides
// when the caller has finished, transcribes, asks the agent and sends back what to say. Speech out uses the browser
// voice for now (a server TTS engine replaces it later, and telephony needs that). No tapping during the call.
"use strict";

const $ = (id) => document.getElementById(id);
const BCP47 = { hi: "hi-IN", bn: "bn-IN", en: "en-IN" };
const T = {
  hi: { ringing: "कॉल लग रही है…", listening: "बोलिए, सुन रहे हैं", thinking: "…", speaking: "बोलो बोल रहा है", ended: "कॉल खत्म", offline: "माफ़ कीजिए, अभी जुड़ नहीं पा रहे। फिर से बोलिए।", mic: "माइक की अनुमति दीजिए" },
  bn: { ringing: "কল যাচ্ছে…", listening: "বলুন, শুনছি", thinking: "…", speaking: "বোলো বলছে", ended: "কল শেষ", offline: "মাফ করবেন, এখন সংযোগ হচ্ছে না। আবার বলুন।", mic: "মাইকের অনুমতি দিন" },
  en: { ringing: "Calling…", listening: "Go ahead, I'm listening", thinking: "…", speaking: "Bolo is speaking", ended: "Call ended", offline: "Sorry, I can't connect right now. Please say that again.", mic: "Please allow the microphone" },
};

let lang = "hi", ws = null, ctx = null, stream = null, node = null, muted = false;
let t0 = 0, timerId = 0, current = null;

// The worklet turns the mic into 16 kHz mono Int16 and posts 20 ms frames (320 samples). We ask the AudioContext to
// run at 16 kHz so the browser resamples with a proper low-pass filter; if it can't, the worklet averages each block
// of input samples (a crude anti-alias filter). Picking every Nth sample aliased the audio and broke recognition.
const WORKLET = `
class Down extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 16000; this.acc = 0; this.buf = new Int16Array(320); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.sum = (this.sum || 0) + ch[i]; this.cnt = (this.cnt || 0) + 1;
      this.acc += 1;
      if (this.acc >= this.ratio) {
        this.acc -= this.ratio;
        const s = Math.max(-1, Math.min(1, this.sum / this.cnt));
        this.sum = 0; this.cnt = 0;
        this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.n === 320) { this.port.postMessage(this.buf.buffer.slice(0)); this.n = 0; }
      }
    }
    return true;
  }
}
registerProcessor("down16k", Down);`;

function setState(s, text) {
  $("phone").dataset.state = s;
  $("state").textContent = text ?? (T[lang][s] || "");
}

function caption(who, text, tag) {
  if (!text) return;
  const d = document.createElement("div");
  d.className = `cap ${who}`;
  d.textContent = text;
  if (tag) { const t = document.createElement("span"); t.className = "t"; t.textContent = tag; d.append(t); }
  $("captions").append(d);
  d.scrollIntoView({ block: "end" });
}

function tick() {
  const s = Math.floor((performance.now() - t0) / 1000);
  $("timer").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function pickVoice(l) {
  const vs = speechSynthesis.getVoices();
  return vs.find((v) => v.lang === BCP47[l]) || vs.find((v) => v.lang.startsWith(l)) || null;
}

// Speak one line; report start/end to the server so it knows when to listen again and can time the turn.
function speak(text, language, opts = {}) {
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = BCP47[language] || BCP47[lang];
    const v = pickVoice(language);
    if (v) u.voice = v;
    u.rate = opts.pace === "slow" ? 0.82 : 0.95;
    let started = false, done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    u.onstart = () => { started = true; opts.id && send({ type: "spoke_start", id: opts.id }); };
    u.onend = u.onerror = finish;
    if (!v && !opts.filler) {
      $("meta").textContent = `No ${language} voice on this device: showing text instead`;
      $("captions").hidden = false; $("cc").setAttribute("aria-pressed", "true");
    }
    speechSynthesis.speak(u);
    // Without a voice some browsers never fire onstart/onend. Don't let the call hang: give the caller time to read
    // the caption, then carry on as if it had been spoken.
    setTimeout(() => {
      if (!started) { opts.id && send({ type: "spoke_start", id: opts.id });
        setTimeout(() => { speechSynthesis.cancel(); finish(); }, Math.max(1500, text.length * 60)); }
    }, 1200);
  });
}

function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }

async function onServer(msg) {
  switch (msg.type) {
    case "connected":
      $("meta").textContent = `speech-to-text: ${msg.stt} · agent: ${msg.agent === "mock" ? "mock" : "Bolo"}`;
      break;
    case "filler":
      speak(msg.text, msg.language, { filler: true });
      break;
    case "heard":
      if (msg.text) caption("you", msg.text, `heard by ${msg.engine}${msg.stt_ms ? ` · ${msg.stt_ms} ms` : ""}`);
      setState("thinking");
      break;
    case "say": {
      current = msg.id;
      const text = msg.text ?? T[msg.language || lang][msg.canned] ?? T[lang].offline;
      caption("bolo", text);
      if (msg.escalation) showAlert(msg.escalation);
      setState("speaking");
      speechSynthesis.cancel(); // drop any filler still playing
      await speak(text, msg.language || lang, { id: msg.id, pace: msg.pace });
      if (current === msg.id) { send({ type: "spoke_end", id: msg.id }); if (ws) setState("listening"); }
      break;
    }
    case "stop":
      if (msg.id === current) { current = null; speechSynthesis.cancel(); setState("listening"); }
      break;
    case "metric":
      $("meta").textContent = `speech end → Bolo speaking: ${msg.end_to_voice_ms} ms`;
      break;
    case "state":
      if (msg.state === "agent_error" || msg.state === "stt_error") $("meta").textContent = `(${msg.state})`;
      break;
    case "end":
      hangup(false);
      break;
  }
}

function showAlert(e) {
  $("alert").hidden = false;
  $("alert").classList.toggle("urgent", e.level !== "emergency");
  $("alert-text").textContent = e.message;
  $("alert-call").hidden = !e.call;
  if (e.call) { $("alert-call").href = `tel:${e.call.number}`; $("alert-call").querySelector("span").textContent = `${e.call.number} · ${e.call.label}`; }
  $("alert-call2").hidden = !e.call || e.call.number === "112";
}

async function startCall() {
  setState("ringing");
  $("pre").hidden = true; $("alert").hidden = true; $("captions").replaceChildren();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  } catch {
    setState("idle", T[lang].mic); $("pre").hidden = false; return;
  }
  try { ctx = new AudioContext({ sampleRate: 16000 }); } catch { ctx = new AudioContext(); }
  await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" })));
  node = new AudioWorkletNode(ctx, "down16k");
  ctx.createMediaStreamSource(stream).connect(node);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/call?lang=${lang}`);
  ws.binaryType = "arraybuffer";
  node.port.onmessage = (e) => { if (!muted && ws && ws.readyState === 1) ws.send(e.data); };
  ws.onmessage = (e) => onServer(JSON.parse(e.data));
  ws.onopen = () => {
    t0 = performance.now(); $("timer").hidden = false; tick(); timerId = setInterval(tick, 1000);
    $("mute").disabled = false;
  };
  ws.onclose = () => { if ($("phone").dataset.state !== "ended") hangup(false); };
}

function hangup(tellServer = true) {
  if (tellServer) send({ type: "hangup" });
  speechSynthesis.cancel();
  current = null;
  clearInterval(timerId);
  if (node) node.port.onmessage = null;
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (ctx) ctx.close();
  const w = ws; ws = null; stream = null; ctx = null; node = null;
  if (w && tellServer) setTimeout(() => w.close(), 300); else if (w) w.close();
  setState("ended");
  $("mute").disabled = true; $("pre").hidden = false;
}

$("callbtn").onclick = () => {
  const s = $("phone").dataset.state;
  if (s === "idle" || s === "ended") startCall(); else hangup(true);
};
$("mute").onclick = (e) => {
  muted = !muted;
  e.currentTarget.setAttribute("aria-pressed", String(muted));
  $("meta").textContent = muted ? "Muted: Bolo can't hear you" : "";
};
$("cc").onclick = (e) => {
  const on = $("captions").hidden;
  $("captions").hidden = !on;
  e.currentTarget.setAttribute("aria-pressed", String(on));
};
document.querySelectorAll(".langs button").forEach((b) => b.addEventListener("click", () => {
  lang = b.dataset.lang;
  document.querySelectorAll(".langs button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
  document.documentElement.lang = lang;
}));
if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};
setState("idle", "");
