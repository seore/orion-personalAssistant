// ======= CONFIG =======
const WEATHER_API_KEY = "2909be0b6d6b4e5597f173222250112";
let weatherQuery = "auto:ip";
const appStartTime = Date.now();

const listenText = document.getElementById("hud-listen-text");
const voiceBtn = document.getElementById("voice-btn");

let speakingTimeout = null;
let isSpeaking = false;

// ======= UTILITY FUNCTIONS =======
function formatDuration(ms) {
  const sec = Math.floor(ms / 1000);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function applyHudState(state) {
  const ring = document.getElementById("hud-ring");
  if (!ring) return;
  ring.classList.remove("listening", "processing", "speaking", "idle");
  ring.classList.add(state);
  isSpeaking = state === "speaking";
}

// ======= TIME & UPTIME =======
function updateTime() {
  const now = new Date();
  const timeEl = document.getElementById("hud-time");
  const dateEl = document.getElementById("hud-date");

  if (timeEl) timeEl.textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  if (dateEl) dateEl.textContent = now.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function updateUptime() {
  const elapsed = Date.now() - appStartTime;
  const uptimeEl = document.getElementById("uptime-running");
  if (uptimeEl) uptimeEl.textContent = formatDuration(elapsed);
}

// ======= SYSTEM STATS =======
async function updateSystemStats() {
  try {
    const stats = await window.orionAPI.getSystemStats();

    const cpuEl = document.getElementById("cpu-usage-text");
    const ramEl = document.getElementById("ram-usage-text");
    const diskEl = document.getElementById("disk-usage-text");
    const cpuBar = document.getElementById("cpu-usage-bar");
    const ramBar = document.getElementById("ram-usage-bar");

    if (cpuEl) cpuEl.textContent = stats.cpuPercent + "%";
    if (ramEl) ramEl.textContent = stats.usedGB.toFixed(1) + " GB";
    if (diskEl) diskEl.textContent = `${stats.usedDisk} / ${stats.totalDisk} GB`;
    if (cpuBar) cpuBar.style.width = stats.cpuPercent + "%";
    if (ramBar) ramBar.style.width = stats.ramPercent + "%";
  } catch (err) {
    console.error("System stats error:", err);
  }
}

// ======= WEATHER =======
function detectLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve();
    navigator.geolocation.getCurrentPosition(
      (pos) => { weatherQuery = `${pos.coords.latitude},${pos.coords.longitude}`; resolve(); },
      (err) => { console.warn("Geolocation failed, using auto:ip"); weatherQuery = "auto:ip"; resolve(); },
      { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 }
    );
  });
}

async function updateWeather() {
  if (!WEATHER_API_KEY) return;

  try {
    const url = `https://api.weatherapi.com/v1/current.json?key=${WEATHER_API_KEY}&q=${encodeURIComponent(weatherQuery)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Weather request failed: " + res.status);
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);

    const loc = data.location;
    const cur = data.current;
    const temp = Math.round(cur.temp_c);
    const feels = Math.round(cur.feelslike_c);
    const humidity = cur.humidity;
    const windMs = (cur.wind_kph / 3.6).toFixed(1);
    const desc = cur.condition.text;
    const cityPretty = `${loc.name}, ${loc.country}`;

    const hudTemp = document.getElementById("hud-temp");
    const hudLocation = document.getElementById("hud-location");
    const weatherTempMain = document.getElementById("weather-temp-main");
    const weatherDescMain = document.getElementById("weather-desc-main");
    const weatherHumidity = document.getElementById("weather-humidity");
    const weatherWind = document.getElementById("weather-wind");
    const weatherFeelslike = document.getElementById("weather-feelslike");

    if (hudTemp) hudTemp.textContent = temp + "°C";
    if (hudLocation) hudLocation.textContent = cityPretty;
    if (weatherTempMain) weatherTempMain.textContent = temp + "°C";
    if (weatherDescMain) weatherDescMain.textContent = `${cityPretty} · ${desc}`;
    if (weatherHumidity) weatherHumidity.textContent = humidity + "%";
    if (weatherWind) weatherWind.textContent = `${windMs} m/s`;
    if (weatherFeelslike) weatherFeelslike.textContent = feels + "°C";
  } catch (err) {
    console.error("Weather error:", err);
  }
}

// ======= CLAUDE DAEMON =======
function startDaemon() {
  const pythonPath = "python3"; 
  const daemonPath = "./voice_daemon.py";
  window.orionAPI.startDaemon(pythonPath, daemonPath);
}

function stopDaemon() {
  window.orionAPI.stopDaemon();
}

// Listen for daemon messages
window.orionAPI.onDaemonMessage((msg) => {
  switch (msg.type) {
    case "status": {
      applyHudState(msg.state);

      if (listenText) {
        if (msg.state === "idle") {
          listenText.textContent = "Titan is idle.";
        } else if (msg.state === "listening") {
          listenText.textContent = "Listening...";
        } else if (msg.state === "processing") {
          listenText.textContent = "Processing...";
        }
      }
      break;
    }

    case "reply": {
      applyHudState("speaking");
      if (listenText) listenText.textContent = msg.text;
      if (speakingTimeout) clearTimeout(speakingTimeout);
      speakingTimeout = setTimeout(() => {
        applyHudState("idle");
        if (listenText) listenText.textContent = "Titan is idle.";
      }, Math.min(15000, Math.max(8000, msg.text.length * 80)));
      break;
    }

    case "transcript": {
      console.log("User said:", msg.text);
      break;
    }

    default: {
      console.log("Daemon message:", msg);
    }
  }
});


// ======= INIT =======
document.addEventListener("DOMContentLoaded", async () => {
  // Start daemon
  startDaemon();
  if (voiceBtn) {
    voiceBtn.addEventListener("click", () => {
      if (isSpeaking) stopDaemon();
      else startDaemon();
    });
  }

  updateTime();
  setInterval(updateTime, 1000);

  updateUptime();
  setInterval(updateUptime, 1000);

  await detectLocation();
  await updateWeather();
  setInterval(updateWeather, 10 * 60 * 1000);

  updateSystemStats();
  setInterval(updateSystemStats, 3000);
});