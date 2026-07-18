import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { chromium } from 'playwright';
import type { EarConfig } from './types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '..', 'dist');

const STATIC_FILES: Record<string, { file: string; contentType: string }> = {
  '/': { file: 'page.html', contentType: 'text/html; charset=utf-8' },
  '/browser-bundle.js': { file: 'browser-bundle.js', contentType: 'text/javascript; charset=utf-8' },
};

function parseArgs(argv: string[]): Omit<EarConfig, 'token'> {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const value = argv[i + 1];
      if (value === undefined) {
        throw new Error(`missing value for --${key}`);
      }
      args.set(key, value);
      i += 1;
    }
  }

  const meetingLink = args.get('meeting-link');
  const wsUrl = args.get('ws-url');
  if (!meetingLink || !wsUrl) {
    throw new Error(
      'usage: ACS_TOKEN=<acsToken> node dist/index.js --meeting-link <teamsMeetingUrl> --ws-url <ws://host:port>',
    );
  }
  return { meetingLink, wsUrl };
}

async function startStaticServer(): Promise<{ url: string; close: () => Promise<void> }> {
  const server = createServer((req, res) => {
    const entry = STATIC_FILES[req.url ?? '/'];
    if (!entry) {
      res.writeHead(404).end('not found');
      return;
    }
    readFile(path.join(distDir, entry.file))
      .then((body) => {
        res.writeHead(200, { 'content-type': entry.contentType }).end(body);
      })
      .catch((error: unknown) => {
        res.writeHead(500).end(String(error));
      });
  });

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (address === null || typeof address === 'string') {
    throw new Error('failed to determine static server address');
  }
  return {
    url: `http://127.0.0.1:${address.port}/`,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}

async function main(): Promise<void> {
  const { meetingLink, wsUrl } = parseArgs(process.argv.slice(2));
  const token = process.env.ACS_TOKEN;
  if (!token) {
    throw new Error('ACS_TOKEN environment variable is required');
  }
  const config: EarConfig = { token, meetingLink, wsUrl };
  const server = await startStaticServer();

  const browser = await chromium.launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  });
  const context = await browser.newContext();
  await context.grantPermissions(['microphone', 'camera'], { origin: server.url });
  const page = await context.newPage();

  page.on('console', (msg) => {
    console.log(msg.text());
  });
  page.on('pageerror', (error) => {
    console.error('[ear:pageerror]', error);
  });

  let shuttingDown = false;
  const shutdown = async (): Promise<void> => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    await browser.close();
    await server.close();
  };

  page.on('console', (msg) => {
    if (msg.text().includes('call disconnected')) {
      void shutdown().then(() => process.exit(0));
    }
  });

  process.on('SIGINT', () => {
    void shutdown().then(() => process.exit(0));
  });

  await page.addInitScript((cfg: EarConfig) => {
    (window as unknown as { __EAR_CONFIG__: EarConfig }).__EAR_CONFIG__ = cfg;
  }, config);

  await page.goto(server.url);
}

main().catch((error) => {
  console.error('[ear] fatal error:', error);
  process.exit(1);
});
