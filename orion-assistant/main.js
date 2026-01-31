const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const si = require("systeminformation");
const os = require("os");

let daemon = null;
let mainWindow = null;
let serverProcess = null;

// Auto-start Claude server
function startClaudeServer() {
  console.log("[Titan] Starting Claude API server...");
  
  const serverPath = app.isPackaged
    ? path.join(process.resourcesPath, 'server', 'index.js')
    : path.join(__dirname, '..', 'orion-server', 'index.js');
  
  console.log("[Titan] Server path:", serverPath);
  
  // Check if server file exists
  const fs = require('fs');
  if (!fs.existsSync(serverPath)) {
    console.error("[Titan] Server file not found at:", serverPath);
    return;
  }
  
  serverProcess = spawn('node', [serverPath], {
    cwd: path.dirname(serverPath),
    env: {
      ...process.env,
      PORT: '3000'
    }
  });
  
  serverProcess.stdout.on('data', (data) => {
    console.log('[Server]', data.toString());
  });
  
  serverProcess.stderr.on('data', (data) => {
    console.error('[Server Error]', data.toString());
  });
  
  serverProcess.on('close', (code) => {
    console.log('[Server] Process exited with code', code);
    serverProcess = null;
  });
  
  // Wait for server to be ready
  return new Promise((resolve) => {
    setTimeout(() => {
      console.log("[Titan] Server should be ready");
      resolve();
    }, 3000);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 700,
    backgroundColor: "#000000ff",
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadFile("index.html");
  // Optional: open DevTools for debugging
  mainWindow.webContents.openDevTools();
}

app.whenReady().then(async () => {
  // Start Claude server first
  await startClaudeServer();
  
  // Then create window
  createWindow();
  
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  // Kill daemon and server
  if (daemon) {
    daemon.kill();
    daemon = null;
  }
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
  if (process.platform !== "darwin") app.quit();
});

/* ==========================
   IPC HANDLERS
========================== */

// Spawn Python daemon
ipcMain.on("start-daemon", (event, { pythonPath, daemonPath }) => {
  if (daemon) {
    console.log("Daemon already running");
    return;
  }

  // Handle asar unpacked path
  let fullPath;
  if (app.isPackaged) {
    fullPath = path.join(process.resourcesPath, 'app.asar.unpacked', 'voice_daemon.py');
  } else {
    fullPath = path.resolve(__dirname, daemonPath);
  }
  
  console.log('Starting daemon at:', fullPath);
  daemon = spawn(pythonPath, [fullPath]);

  // Forward stdout messages to renderer
  daemon.stdout.on("data", (data) => {
    const lines = data.toString().split("\n");
    lines.forEach((line) => {
      if (line.trim()) {
        try {
          const msg = JSON.parse(line);
          // Send message to renderer
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send("daemon-message", msg);
          }
        } catch (err) {
          console.log("Daemon stdout:", line);
        }
      }
    });
  });

  // Log stderr
  daemon.stderr.on("data", (data) => {
    console.error("Daemon stderr:", data.toString());
  });

  // Handle process exit
  daemon.on("close", (code) => {
    console.log("Daemon process exited with code", code);
    daemon = null;
  });

  console.log("Daemon started");
});

// Stop daemon
ipcMain.on("stop-daemon", () => {
  if (daemon) {
    daemon.kill();
    daemon = null;
    console.log("Daemon stopped");
  }
});

// Get system stats
ipcMain.handle("get-system-stats", async () => {
  const [load, mem, fsInfo] = await Promise.all([
    si.currentLoad(),
    si.mem(),
    si.fsSize()
  ]);

  const cpuPercent = Math.round(load.currentLoad);
  const totalGB = mem.total / 1024 ** 3;
  const usedGB = (mem.total - mem.available) / 1024 ** 3;
  const ramPercent = Math.round((usedGB / totalGB) * 100);
  
  const disk = fsInfo[0];
  const usedDisk = (disk.used / 1024 ** 3).toFixed(0);
  const totalDisk = (disk.size / 1024 ** 3).toFixed(0);

  return { cpuPercent, ramPercent, usedGB, totalDisk, usedDisk };
});