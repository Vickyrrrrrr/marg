const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const readline = require("node:readline");
let backend;
const lock = app.requestSingleInstanceLock();
if (!lock) app.quit();
function startBackend() {
  return new Promise((resolve, reject) => {
    const executable = app.isPackaged
      ? path.join(
          process.resourcesPath,
          "backend",
          process.platform === "win32"
            ? "ledgerly-backend.exe"
            : "ledgerly-backend",
        )
      : process.platform === "win32"
        ? "python"
        : "python3";
    backend = spawn(
      executable,
      app.isPackaged ? [] : [path.join(__dirname, "..", "server.py")],
      {
        env: {
          ...process.env,
          PORT: "0",
          LEDGERLY_DATA_DIR: app.getPath("userData"),
          LEDGERLY_DESKTOP: "1",
        },
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      },
    );
    const timer = setTimeout(
      () => reject(Error("The local database service did not start.")),
      20000,
    );
    const lines = readline.createInterface({ input: backend.stdout });
    lines.on("line", (line) => {
      if (line.startsWith("LEDGERLY_READY=")) {
        clearTimeout(timer);
        resolve(line.slice(15));
      }
    });
    backend.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
    backend.on("exit", (code) => {
      clearTimeout(timer);
      reject(Error("Local service exited: " + code));
    });
  });
}
app.whenReady().then(async () => {
  try {
    const url = await startBackend();
    const win = new BrowserWindow({
      width: 1380,
      height: 920,
      minWidth: 850,
      minHeight: 650,
      title: "Ledgerly",
      backgroundColor: "#f7f9f7",
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
      },
    });
    win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    win.webContents.on("will-navigate", (event, target) => {
      if (new URL(target).origin !== new URL(url).origin)
        event.preventDefault();
    });
    await win.loadURL(url);
  } catch (e) {
    dialog.showErrorBox("Ledgerly could not start", e.message);
    app.quit();
  }
});
app.on("second-instance", () => {
  const win = BrowserWindow.getAllWindows()[0];
  if (win) {
    win.restore();
    win.focus();
  }
});
app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => backend?.kill());
