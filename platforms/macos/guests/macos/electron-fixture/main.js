const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const stateRoot = path.join(
  os.homedir(), 'Library', 'Caches', 'machine-control-electron-fixture'
);
const statePath = path.join(stateRoot, 'state.json');
let state = { framework: 'Electron', count: 0, effect: 'launched' };

function writeState() {
  fs.mkdirSync(stateRoot, { recursive: true });
  const temporary = `${statePath}.new`;
  fs.writeFileSync(temporary, `${JSON.stringify(state)}\n`, { mode: 0o600 });
  fs.renameSync(temporary, statePath);
}

function updateState(effect) {
  if (effect === 'incremented') state.count += 1;
  if (effect === 'reset') state.count = 0;
  state.effect = effect;
  writeState();
  return state;
}

app.setName('Machine Control Electron Fixture');
ipcMain.handle('fixture:update', (_event, effect) => updateState(effect));

app.whenReady().then(() => {
  writeState();
  const window = new BrowserWindow({
    width: 520,
    height: 320,
    title: 'Machine Control Electron Fixture',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });
  window.loadFile('index.html');
});

app.on('window-all-closed', () => app.quit());
