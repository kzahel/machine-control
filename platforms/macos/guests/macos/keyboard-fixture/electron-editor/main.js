const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv.find(arg => arg.startsWith('--fixture-root=')).slice('--fixture-root='.length);
app.setPath('userData', path.join(root, 'profile'));
app.commandLine.appendSwitch('use-mock-keychain');
app.commandLine.appendSwitch('password-store', 'basic');
let window;
let state = { pid: process.pid, text: '', saves: 0, finds: 0, ready: false };
function write() {
  const file = path.join(root, 'editor-state.json');
  fs.writeFileSync(file + '.new', JSON.stringify(state), { mode: 0o600 });
  fs.renameSync(file + '.new', file);
}
ipcMain.on('editor:input', (_event, text) => { state.text = text; write(); });
ipcMain.on('editor:ready', () => { state.ready = true; write(); });
ipcMain.on('editor:find', (_event, query) => { state.query = query; write(); });
app.whenReady().then(() => {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Keyboard Editor', submenu: [{ role: 'quit' }] },
    { label: 'File', submenu: [{ label: 'Save', accelerator: 'Command+S', click: () => {
      state.saves += 1; state.savedText = state.text; write();
    } }] },
    { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' },
      { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      { label: 'Find', accelerator: 'Command+F', click: () => {
        state.finds += 1; state.query = ''; write(); window.webContents.send('editor:find');
      } }] }
  ]));
  window = new BrowserWindow({ width: 680, height: 440, title: 'Machine Control Keyboard Editor',
    webPreferences: { contextIsolation: true, nodeIntegration: false, preload: path.join(__dirname, 'preload.js') } });
  window.loadFile('index.html');
  write();
});
app.on('window-all-closed', () => app.quit());
