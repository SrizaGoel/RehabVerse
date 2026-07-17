/**
 * RehabVerse — Electron Preload Script
 *
 * Runs in a privileged context before the renderer (React) loads.
 * Use contextBridge to safely expose any Node/Electron APIs to the renderer.
 * Keep this minimal — only expose what React actually needs.
 */

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,          // 'win32', 'darwin', 'linux'
  isElectron: true,                    // lets React know it's in desktop mode
});
