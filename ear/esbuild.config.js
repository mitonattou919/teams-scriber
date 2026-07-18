import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outdir = path.join(__dirname, 'dist');

await mkdir(outdir, { recursive: true });

await build({
  entryPoints: [path.join(__dirname, 'src/browser/meeting-client.ts')],
  outfile: path.join(outdir, 'browser-bundle.js'),
  bundle: true,
  platform: 'browser',
  format: 'iife',
  target: 'chrome120',
  sourcemap: true,
});

await build({
  entryPoints: [path.join(__dirname, 'src/index.ts')],
  outfile: path.join(outdir, 'index.js'),
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node20',
  external: ['playwright'],
  sourcemap: true,
});

await copyFile(path.join(__dirname, 'src/page.html'), path.join(outdir, 'page.html'));

console.log('build complete');
