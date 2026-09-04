// Headless-Chrome screenshots of app routes in both themes via CDP. No dependencies beyond the
// `ws` Next.js already ships. Usage: SESSIONID=… node scripts/screenshots.mjs [baseUrl]
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import WebSocket from "next/dist/compiled/ws/index.js";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = process.argv[2] ?? "http://localhost:3000";
const PORT = 9333;
const ROUTES = ["dashboard", "inbox", "forecast", "reconciliation"];
const THEMES = ["light", "dark"];
const VIEWPORT = { width: 1440, height: 1100 };
const SETTLE_MS = 3500;
const OUT_DIR = new URL("../screenshots/", import.meta.url).pathname;

const sessionId = process.env.SESSIONID;
if (!sessionId) throw new Error("SESSIONID env var required (log in with curl first)");

const chrome = spawn(CHROME, [`--headless=new`, `--remote-debugging-port=${PORT}`, "--no-first-run", "--no-default-browser-check", `--user-data-dir=/tmp/nx-shots-${Date.now()}`, "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForDevtools() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const res = await fetch(`http://localhost:${PORT}/json/version`);
      if (res.ok) return;
    } catch {}
    await sleep(200);
  }
  throw new Error("Chrome devtools endpoint never came up");
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url, { perMessageDeflate: false });
    let id = 0;
    const pending = new Map();
    const listeners = new Set();
    ws.on("open", () => resolve({ send, on: (fn) => listeners.add(fn), close: () => ws.close() }));
    ws.on("error", reject);
    ws.on("message", (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.id && pending.has(msg.id)) {
        const { resolve: ok, reject: fail } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? fail(new Error(msg.error.message)) : ok(msg.result);
      } else if (msg.method) listeners.forEach((fn) => fn(msg));
    });
    function send(method, params = {}) {
      id += 1;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((ok, fail) => pending.set(id, { resolve: ok, reject: fail }));
    }
  });
}

async function main() {
  await waitForDevtools();
  const target = await (await fetch(`http://localhost:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
  const cdp = await connect(target.webSocketDebuggerUrl);
  await cdp.send("Network.enable");
  await cdp.send("Page.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", { ...VIEWPORT, deviceScaleFactor: 1, mobile: false });
  const { hostname } = new URL(BASE);
  await cdp.send("Network.setCookie", { name: "sessionid", value: sessionId, domain: hostname, path: "/", httpOnly: true });
  mkdirSync(OUT_DIR, { recursive: true });
  for (const theme of THEMES) {
    for (const route of ROUTES) {
      const loaded = new Promise((resolve) => cdp.on((msg) => msg.method === "Page.loadEventFired" && resolve()));
      await cdp.send("Page.navigate", { url: `${BASE}/${route}?theme=${theme}` });
      await loaded;
      await sleep(SETTLE_MS);
      const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
      const file = `${OUT_DIR}${route}-${theme}.png`;
      writeFileSync(file, Buffer.from(data, "base64"));
      console.log("wrote", file);
    }
  }
  cdp.close();
}

main()
  .catch((error) => { console.error(error); process.exitCode = 1; })
  .finally(() => chrome.kill());
