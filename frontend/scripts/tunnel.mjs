import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, createWriteStream, writeFileSync, readFileSync, renameSync, unlinkSync } from 'node:fs';
import { pipeline } from 'node:stream/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = join(__dirname, '..');
const ENV_PATH = join(FRONTEND_DIR, '.env');
const MARKER_PATH = join(FRONTEND_DIR, '.tunnel.url');

const RELEASE_URL = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe';
const URL_RE = /https:\/\/[a-z0-9-]+\.trycloudflare\.com/;

function getCloudflaredPath() {
  if (process.env.VISIONFORGE_CLOUDFLARED && existsSync(process.env.VISIONFORGE_CLOUDFLARED)) {
    return process.env.VISIONFORGE_CLOUDFLARED;
  }
  const home = process.env.USERPROFILE || os.homedir();
  const candidates = [
    join(home, '.visionforge', 'bin', 'cloudflared.exe'),
    join(process.env.LOCALAPPDATA || home, 'visionforge', 'cloudflared.exe'),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return candidates[0];
}

async function ensureCloudflared() {
  const target = getCloudflaredPath();
  if (existsSync(target)) return target;

  mkdirSync(dirname(target), { recursive: true });
  console.log('[tunnel] First run: downloading cloudflared (~55MB)…');
  const res = await fetch(RELEASE_URL, { redirect: 'follow' });
  if (!res.ok || !res.body) {
    throw new Error(`[tunnel] Download failed: HTTP ${res.status}. Set VISIONFORGE_CLOUDFLARED to an existing cloudflared binary.`);
  }
  const tmp = `${target}.tmp`;
  await pipeline(res.body, createWriteStream(tmp));
  renameSync(tmp, target);
  console.log(`[tunnel] Installed: ${target}`);
  return target;
}

function updateEnv(url) {
  const urlLine = `VITE_PUBLIC_URL=${url}`;
  let lines = [];
  if (existsSync(ENV_PATH)) {
    lines = readFileSync(ENV_PATH, 'utf8').split(/\r?\n/);
  }
  const out = [];
  let replaced = false;
  for (const line of lines) {
    if (/^VITE_PUBLIC_URL\s*=/.test(line.trim())) {
      if (!replaced) {
        out.push(urlLine);
        replaced = true;
      }
    } else {
      out.push(line);
    }
  }
  if (!replaced) out.push(urlLine);
  writeFileSync(ENV_PATH, `${out.join('\n').replace(/\n+$/, '')}\n`, 'utf8');
}

function cleanup(marker) {
  try {
    if (existsSync(marker)) unlinkSync(marker);
  } catch {
    /* ignore */
  }
}

async function main() {
  try {
    const exe = await ensureCloudflared();
    const args = ['tunnel', '--url', 'http://localhost:5173', '--no-autoupdate'];
    const proc = spawn(exe, args, { stdio: ['ignore', 'pipe', 'pipe'] });

    console.log('[tunnel] Starting Cloudflare quick tunnel → http://localhost:5173');
    if (existsSync(MARKER_PATH)) unlinkSync(MARKER_PATH);

    let announced = false;

    const handleChunk = (chunk) => {
      const text = chunk.toString();
      const match = text.match(URL_RE);
      if (match && !announced) {
        announced = true;
        const url = match[0];
        updateEnv(url);
        writeFileSync(MARKER_PATH, url, 'utf8');
        console.log('');
        console.log('============================================================');
        console.log(`  MOBILE HTTPS URL: ${url}`);
        console.log('  (Written to frontend/.env as VITE_PUBLIC_URL)');
        console.log('  Scan the QR in the app — it now encodes this URL.');
        console.log('============================================================');
        console.log('');
      }
      process.stdout.write(`[cloudflared] ${text}`);
    };

    proc.stdout.on('data', handleChunk);
    proc.stderr.on('data', handleChunk);

    proc.on('error', (err) => {
      console.error(`[tunnel] Failed to launch cloudflared: ${err.message}`);
      process.exit(1);
    });

    proc.on('close', (code) => {
      cleanup(MARKER_PATH);
      console.log(`[tunnel] cloudflared exited (code ${code}). Tunnel closed.`);
      process.exit(code || 0);
    });

    const shutdown = () => {
      cleanup(MARKER_PATH);
      proc.kill();
      process.exit(0);
    };
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (err) {
    console.error(err.message || err);
    process.exit(1);
  }
}

main();