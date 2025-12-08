const { spawn } = require("child_process");
const path = require("path");
const si = require("systeminformation");
const os = require('os'); 

// ========= PATHS / CONFIG =========
let pythonPath;
if (os.platform() === "darwin") {
  pythonPath = path.join(__dirname, "..", "venv", "bin", "python3");
} else if (os.platform() === "win32") {
  pythonPath = path.join(__dirname, "..", "venv", "Scripts", "python.exe");
} else {
  pythonPath = "python3";
}

const projectRoot = path.join(__dirname, ".."); 
//const pythonPath = path.join(projectRoot, "venv", "bin", "python3");
const scriptPath = path.join(projectRoot, "voice_daemon.py");
const daemonScriptPath = path.join(__dirname, "..", "voice_daemon.py");


const WEATHER_API_KEY = "2909be0b6d6b4e5597f173222250112";
let weatherQuery = "auto:ip";

const appStartTime = Date.now();

const listenText = document.getElementById("hud-listen-text");

let daemon = null;
let speakingTimeout = null;
let voiceButtonInitialized = false;

// ========= TIME / DATE =========
function updateTime() {
  const now = new Date();
  const timeEl = document.getElementById("hud-time");
  const dateEl = document.getElementById("hud-date");

  if (timeEl) {
    timeEl.textContent = now.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }
}

// ========= SYSTEM STATS =========
async function updateSystemStats() {
  try {
    const [load, mem, fsInfo] = await Promise.all([
      si.currentLoad(),
      si.mem(),
      si.fsSize(),
    ]);

    // CPU
    const cpuPercent = Math.round(load.currentLoad);
    const cpuUsageText = document.getElementById("cpu-usage-text");
    const cpuPercentSmall = document.getElementById("cpu-percent-small");
    const cpuUsageBar = document.getElementById("cpu-usage-bar");
    const loadPercent = document.getElementById("load-percent");
    const loadBar = document.getElementById("load-bar");

    if (cpuUsageText) cpuUsageText.textContent = cpuPercent + "%";
    if (cpuPercentSmall) cpuPercentSmall.textContent = cpuPercent + "%";
    if (cpuUsageBar) cpuUsageBar.style.width = cpuPercent + "%";
    if (loadPercent) loadPercent.textContent = cpuPercent + "%";
    if (loadBar) loadBar.style.width = cpuPercent + "%";

    // RAM
    const totalGB = mem.total / 1024 ** 3;
    const usedGB = (mem.total - mem.available) / 1024 ** 3;
    const ramPercent = Math.round((usedGB / totalGB) * 100);

    const ramUsageText = document.getElementById("ram-usage-text");
    const memPercentSmall = document.getElementById("mem-percent-small");
    const ramUsageBar = document.getElementById("ram-usage-bar");

    if (ramUsageText) ramUsageText.textContent = usedGB.toFixed(1) + " GB";
    if (memPercentSmall) memPercentSmall.textContent = ramPercent + "%";
    if (ramUsageBar) ramUsageBar.style.width = ramPercent + "%";

    // DISK (first volume)
    if (fsInfo && fsInfo.length > 0) {
      const disk = fsInfo[0];
      const usedDisk = (disk.used / 1024 ** 3).toFixed(0);
      const totalDisk = (disk.size / 1024 ** 3).toFixed(0);
      const diskUsageText = document.getElementById("disk-usage-text");
      if (diskUsageText) {
        diskUsageText.textContent = `${usedDisk} / ${totalDisk} GB`;
      }
    }
  } catch (err) {
    console.error("System stats error:", err);
  }
}

// ========= WEATHER =========
function detectLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      console.warn("Geolocation not available, using auto:ip");
      return resolve();
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        weatherQuery = `${pos.coords.latitude},${pos.coords.longitude}`;
        console.log("Using precise coords for weather:", weatherQuery);
        resolve();
      },
      (err) => {
        console.warn("Geolocation error, using auto:ip instead:", err);
        weatherQuery = "auto:ip";
        resolve();
      },
      {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 60_000,
      }
    );
  });
}

async function updateWeather() {
  if (!WEATHER_API_KEY) {
    console.warn("No WEATHER_API_KEY set.");
    return;
  }

  try {
    const url = `https://api.weatherapi.com/v1/current.json?key=${WEATHER_API_KEY}&q=${encodeURIComponent(
      weatherQuery
    )}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Weather request failed: " + res.status);
    const data = await res.json();

    if (data.error) {
      throw new Error("WeatherAPI error: " + data.error.message);
    }

    const loc = data.location;
    const cur = data.current;

    const temp = Math.round(cur.temp_c);
    const feels = Math.round(cur.feelslike_c);
    const humidity = cur.humidity;
    const windMs = (cur.wind_kph / 3.6).toFixed(1);
    const desc = cur.condition.text;
    const cityPretty = `${loc.name}, ${loc.country}`;

    const hudTemp = document.getElementById("hud-temp");
    const hudLoc = document.getElementById("hud-location");
    if (hudTemp) hudTemp.textContent = temp + "°C";
    if (hudLoc) hudLoc.textContent = cityPretty;

    const tempMain = document.getElementById("weather-temp-main");
    const descMain = document.getElementById("weather-desc-main");
    const humEl = document.getElementById("weather-humidity");
    const windEl = document.getElementById("weather-wind");
    const feelsEl = document.getElementById("weather-feelslike");

    if (tempMain) tempMain.textContent = temp + "°C";
    if (descMain) descMain.textContent = `${cityPretty} · ${desc}`;
    if (humEl) humEl.textContent = humidity + "%";
    if (windEl) windEl.textContent = `${windMs} m/s`;
    if (feelsEl) feelsEl.textContent = feels + "°C";
  } catch (err) {
    console.error("Weather error:", err);
  }
}

// ========= UPTIME =========
function formatDuration(ms) {
  const sec = Math.floor(ms / 1000);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function updateUptime() {
  const elapsed = Date.now() - appStartTime;
  const uptimeEl = document.getElementById("uptime-running");
  const sessionEl = document.getElementById("session-count");
  const commandsEl = document.getElementById("command-count");

  if (uptimeEl) uptimeEl.textContent = formatDuration(elapsed);
  if (sessionEl) sessionEl.textContent = "1";
  if (commandsEl) commandsEl.textContent = ""; // not tracking yet
}

/*
// ========= CONVERSATION PANEL =========
function addMessage(sender, text) {
  const body = document.getElementById("conversation-body");
  if (!body || !text) return; 

  const wrapper = document.createElement("div");
  wrapper.classList.add("message");
  if (sender === "orion") wrapper.classList.add("orion");
  if (sender === "user") wrapper.classList.add("user");

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = text;

  const timestamp = document.createElement("div");
  timestamp.classList.add("timestamp");
  timestamp.textContent = new Date().toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  wrapper.appendChild(bubble);
  wrapper.appendChild(timestamp);
  body.appendChild(wrapper);

  body.scrollTop = body.scrollHeight;
}
*/

function applyHudState(state) {
  const ring = document.getElementById("hud-ring");
  if (!ring) return;

  ring.classList.remove("listening", "processing", "speaking", "idle");
  ring.classList.add(state);

  console.log("[HUD] state =", state, "classes:", ring.className);

  if (state === "speaking") {
    isSpeaking = true;
  }
}

// ========= VOICE DAEMON / BUTTON =========
function startVoiceDaemon() {
if (daemon) return; 

  console.log("Spawning Python daemon:", pythonPath, daemonScriptPath);
  daemon = spawn(pythonPath, [daemonScriptPath]);

  //const ring = document.getElementById("hud-ring");
  applyHudState("idle");
  if (listenText) listenText.textContent = "Orion is idle.";


  let buffer = "";

  daemon.stdout.on("data", (data) => {
    buffer += data.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.trim()) continue;

      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        console.log("DAEMON:", line);
        continue;
      }

      // ---- ORION STATUS UPDATES 
      if (msg.type === "status") {
         if (isSpeaking) {
          console.log("[HUD] ignoring status while speaking:", msg.state);
          continue;
        }
        if (msg.state === "listening") {
          applyHudState("listening");
          if (listenText) {
            listenText.textContent = "Listening... (say 'Hey Orion ...')";
          }
        } else if (msg.state === "processing") {
          applyHudState("processing");
          if (listenText) {
            listenText.textContent = "Processing your request…";
          }
        } else if (msg.state === "idle") {
          applyHudState("idle");
          if (listenText) {
            listenText.textContent = "Orion is idle.";
          }
        }
        continue;
      }

      // ---- ORION'S RESPONSE ----
      if (msg.type === "reply") {
        applyHudState("speaking");
        if (listenText) {
          listenText.textContent = "Orion is speaking…";
        }

        if (speakingTimeout) clearTimeout(speakingTimeout);
        const len = (msg.text || "").length;
        const ms = Math.min(15000, Math.max(8000, len * 80));

        speakingTimeout = setTimeout(() => {
          //isSpeaking = false;
          applyHudState("idle");
          if (listenText) {
            listenText.textContent = "Orion is idle.";
          }
        }, ms);

        continue;
      }

      // ---- USER TRANSCRIPT ----
      if (msg.type === "transcript") {
        console.log("Orion heard:", msg.text);
        // optional: show this somewhere in the UI
        continue;
      }

      // ---- ERRORS FROM DAEMON ----
      if (msg.type === "error") {
        console.error("DAEMON ERROR:", msg.message || msg.text || msg);
        applyHudState("idle");
        if (listenText) {
          listenText.textContent = "Orion is idle.";
        }
      }
    }
  });

  daemon.stderr.on("data", (data) => {
    const text = data.toString().trim();

    // Noisy STT logs → treat as info
    if (
      text.includes("Listening... (speak now)") ||
      text.includes("Listening timed out while waiting for speech.") ||
      text.includes("I didn't catch that.") ||
      text.startsWith("You said:")
    ) {
      console.log("Orion STT:", text);
      return;
    }

    console.error("REAL DAEMON ERROR:", text);
  });

  daemon.on("close", (code) => {
    console.log("Python daemon exited with code", code);
    daemon = null;
    isSpeaking = false;
    if (speakingTimeout) clearTimeout(speakingTimeout);
    applyHudState("idle");
    if (listenText) listenText.textContent = "Orion is offline.";
  });
}

function stopVoiceDaemon() {
  if (!daemon) return;
  console.log("Stopping Orion daemon");
  daemon.kill();   // send SIGTERM
  daemon = null;
}

function setupVoiceButton() {
  const voiceBtn = document.getElementById("voice-btn");
  if (!voiceBtn) return;

  voiceBtn.addEventListener("click", () => {
    if (daemon) {
      stopVoiceDaemon();
    } else {
      startVoiceDaemon();
    }
  });
}

// ======= ORION VOICE =======
/*
function speakIntroOnce() {
  try {
    const child = spawn(pythonPath, ["-m", "orion.intro"], {
      cwd: projectRoot,
    });

    child.stderr.on("data", (d) => {
      console.error("INTRO ERR:", d.toString());
    });
  } catch (e) {
    console.error("Failed to run intro voice:", e);
  }
}
*/


// ========= INIT =========
document.addEventListener("DOMContentLoaded", async () => {
  //speakIntroOnce();

  updateTime();
  setInterval(updateTime, 1000);

  updateSystemStats();
  setInterval(updateSystemStats, 3000);

  await detectLocation();
  await updateWeather();
  setInterval(updateWeather, 10 * 60 * 1000);

  updateUptime();
  setInterval(updateUptime, 1000);

  startVoiceDaemon();

  setupVoiceButton();

  //speakIntroOnce();
});
