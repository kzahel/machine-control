const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('editor', {
  input: text => ipcRenderer.send('editor:input', text),
  ready: () => ipcRenderer.send('editor:ready'),
  find: query => ipcRenderer.send('editor:find', query),
  onFind: callback => ipcRenderer.on('editor:find', callback)
});
