const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('orionAPI', {
  // System stats
  getSystemStats: () => ipcRenderer.invoke('get-system-stats'),
  
  // Daemon control
  startDaemon: (pythonPath, daemonPath) => ipcRenderer.send('start-daemon', { pythonPath, daemonPath }),
  stopDaemon: () => ipcRenderer.send('stop-daemon'),
  
  // Listen for daemon messages
  onDaemonMessage: (callback) => {
    ipcRenderer.on('daemon-message', (event, message) => {
      callback(message);
    });
  }
});