/**
 * RehabVerse — Electron Main Process
 *
 * Responsibilities:
 *  1. Spawn the Python Flask backend silently (no console window)
 *  2. Wait for Flask to be ready, then open the browser window
 *  3. Clean up the backend process on app quit
 */

const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

let backendProcess = null;
let mainWindow = null;

// ─── Backend ────────────────────────────────────────────────────────────────

function getBackendPath() {
  if (app.isPackaged) {
    // Production: backend is in app's extraResources folder
    return path.join(process.resourcesPath, "backend", "run_server", "run_server.exe");
  }
  // Development: use pre-built PyInstaller dist (or fall back to raw python)
  const distExe = path.join(__dirname, "../../backend/dist/run_server/run_server.exe");
  return distExe;
}

function startBackend() {
  const backendPath = getBackendPath();
  console.log("[RehabVerse] Starting backend:", backendPath);

  backendProcess = spawn(backendPath, [], {
    detached: false,
    stdio: "ignore",     // suppress all output — no terminal window
    windowsHide: true,   // hide Windows console window
  });

  backendProcess.on("error", (err) => {
    console.error("[RehabVerse] Backend error:", err.message);
  });

  backendProcess.on("exit", (code) => {
    console.log("[RehabVerse] Backend exited with code:", code);
  });
}

// Poll until Flask responds on port 5000
function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (remaining) => {
      if (remaining <= 0) {
        reject(new Error("Backend did not start in time"));
        return;
      }
      const req = http.get("http://127.0.0.1:5000/", (res) => {
        resolve();
      });
      req.on("error", () => {
        setTimeout(() => check(remaining - 1), 500);
      });
      req.setTimeout(500, () => {
        req.destroy();
        setTimeout(() => check(remaining - 1), 500);
      });
    };
    check(retries);
  });
}

// ─── Window ─────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
    },
    icon: path.join(__dirname, "../public/icon.png"),
    title: "RehabVerse",
    backgroundColor: "#0a1f1a",   // match app dark background while loading
    show: false,                   // show only when ready-to-show fires
    autoHideMenuBar: true,         // hide menu bar (press Alt to toggle)
  });

  // Load the app
  if (app.isPackaged) {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  } else {
    mainWindow.loadURL("http://localhost:5173");
  }
  mainWindow.webContents.openDevTools();

  // Show window only once it's fully rendered (prevents white flash)
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // Open external links in the system browser, not Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ─── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend();

  // Wait for Flask to be ready before opening window
  try {
    await waitForBackend(40);  // up to 20 seconds
    console.log("[RehabVerse] Backend is ready");
  } catch (err) {
    console.error("[RehabVerse] Backend timeout — opening window anyway:", err.message);
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  // Kill Flask backend
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  // On Windows/Linux, quit when all windows are closed
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
