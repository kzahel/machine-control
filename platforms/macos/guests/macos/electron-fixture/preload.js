const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('fixture', {
  update: (effect) => ipcRenderer.invoke('fixture:update', effect)
});
