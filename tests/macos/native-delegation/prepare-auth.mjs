#!/usr/bin/env node
// Own a credentialed, isolated fixture profile using YA's real AuthService.
import { randomBytes } from 'node:crypto';
import { mkdir, stat, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [modulePath, directory] = process.argv.slice(2);
if (!modulePath || !directory || process.argv.length !== 4) {
  throw new Error('Usage: prepare-auth.mjs YA_AUTH_SERVICE_MODULE PRIVATE_DIRECTORY');
}
const root = resolve(directory);
const information = await stat(root);
if (!information.isDirectory() || (information.mode & 0o077) !== 0) {
  throw new Error('Create a fresh mode-0700 fixture directory first');
}
const dataDir = join(root, 'data');
await mkdir(dataDir, { mode: 0o700 }); // existing profiles are never overwritten
const { AuthService } = await import(pathToFileURL(resolve(modulePath)).href);
const service = new AuthService({ dataDir });
await service.initialize();
if (!(await service.enableAuth(randomBytes(32).toString('hex')))) {
  throw new Error('Credentialed fixture setup failed');
}
const cookie = await service.createSession('native-delegation-conformance');
await writeFile(join(root, 'auth.private.json'), JSON.stringify({ cookie }), {
  mode: 0o600, flag: 'wx',
});
console.log('Credentialed fixture profile and private owner cookie prepared');
