// Test the real pinned Pi CLI within an internal-only Docker network.
// No upstream provider credentials, account information or paid calls exist here.
import net from 'node:net';
import { spawn } from 'node:child_process';

function canConnect(host, port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    let done = false;
    function finish(value) {
      if (done) return;
      done = true;
      socket.destroy();
      resolve(value);
    }
    socket.setTimeout(1000);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
  });
}

function piSession() {
  return new Promise((resolve, reject) => {
    const child = spawn('pi', [
      '--print', '--mode', 'json', '--session-dir', '/tmp/pi-sessions',
      '--provider', 'mock-gateway', '--model', 'test-model-1'
    ], { env: process.env });
    const chunks = [];
    let bytes = 0;
    child.stdout.on('data', (chunk) => {
      bytes += chunk.length;
      if (bytes > 2_000_000) {
        child.kill('SIGKILL');
        reject(new Error('Pi output exceeded safe test limit'));
        return;
      }
      chunks.push(chunk);
    });
    child.stderr.on('data', (chunk) => {
      // Preserve only short local error details if the session fails.
      if (bytes < 2_000_000) chunks.push(chunk);
    });
    child.once('error', reject);
    child.once('exit', (code) => {
      const output = Buffer.concat(chunks).toString('utf8');
      if (code !== 0 || !output.includes('"stopReason":"stop"')) {
        reject(new Error(`Pi session did not finish successfully: exit=${code}; tail=${output.slice(-900)}`));
      } else {
        resolve();
      }
    });
    child.stdin.end('Respond with OK. Do not use tools.\n');
  });
}

const ip = process.env.PROVIDER_IP;
if (!ip) throw new Error('missing raw-IP bypass target');
for (const [host, port, label] of [
  ['provider', 8770, 'provider DNS name'],
  [ip, 8770, 'provider raw IP'],
  ['1.1.1.1', 443, 'public internet raw IP'],
]) {
  if (await canConnect(host, port)) {
    throw new Error(`ISOLATION FAILURE: real Pi container reached ${label}`);
  }
}
if (process.env.OPENAI_API_KEY || process.env.ANTHROPIC_API_KEY) {
  throw new Error('upstream provider credentials leaked');
}
await piSession();
console.log('PASS: real Pi within internal-only Docker network completed via metered mock gateway');
