// Serves the static export the way GitHub Pages does, and refuses what the host refuses.
//
// HEAD gets a 405, because Pages answers it with an error and nothing on the site may depend on it.
// The mock API under /mock-api answers its first request with a 503, the way a Vercel function
// answers while it starts cold, so the desk has to probe twice. After that the mock replays the
// recorded session: /health, a chat turn by its question, a resume by its thread, a trace by its id,
// each as the live API would send it, the chat as server sent events.
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "out");
const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "/readback";
const port = Number(process.env.READBACK_E2E_PORT ?? 4174);

if (!existsSync(join(root, "index.html"))) {
  console.error("out/index.html is missing: run `npm run build:e2e` first");
  process.exit(1);
}

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".parquet": "application/vnd.apache.parquet",
};

const session = JSON.parse(readFileSync(join(root, "data", "recorded_session.json"), "utf8"));
const CORS = { "Access-Control-Allow-Origin": "*" };

let firstApiRequest = true;
function mockApi(req, res, path) {
  const json = (status, body) => {
    res.writeHead(status, { "Content-Type": "application/json", ...CORS });
    res.end(JSON.stringify(body));
  };
  const sse = (events) => {
    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", ...CORS });
    let i = 0;
    const next = () => {
      if (i >= events.length) {
        res.write(`event: done\ndata: ${JSON.stringify({ statement: session.health.statement })}\n\n`);
        return res.end();
      }
      const e = events[i++];
      res.write(`event: ${e.event}\ndata: ${JSON.stringify(e)}\n\n`);
      setTimeout(next, 40);
    };
    next();
  };
  if (req.method === "OPTIONS") {
    res.writeHead(204, { ...CORS, "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "content-type" });
    return res.end();
  }
  if (firstApiRequest) {
    firstApiRequest = false;
    return json(503, { error: "the function is starting" });
  }
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    if (req.method === "GET" && path === "/health") return json(200, session.health);
    const trace = /^\/v1\/traces\/([0-9a-f]+)$/.exec(path);
    if (req.method === "GET" && trace) return json(200, { trace_id: trace[1], spans: session.traces[trace[1]] ?? [] });
    let parsed = {};
    try {
      parsed = JSON.parse(body || "{}");
    } catch {
      return json(422, { error: "the body is not JSON" });
    }
    if (req.method === "POST" && path === "/v1/chat") {
      const turn = session.turns.find((t) => t.question === parsed.question);
      if (!turn) return json(404, { error: "the mock has no recording of that question" });
      return sse(turn.events.filter((e) => e.event !== "done"));
    }
    const resume = /^\/v1\/chat\/([0-9a-f]+)\/resume$/.exec(path);
    if (req.method === "POST" && resume) {
      const turn = session.turns.find((t) => t.resume && t.events.some((e) => e.thread_id === resume[1]));
      if (!turn) return json(404, { error: "no interrupted turn on that thread" });
      return sse(turn.resume.filter((e) => e.event !== "done"));
    }
    return json(404, { error: `no recorded response for ${req.method} ${path}` });
  });
}

function send404(res) {
  const page = join(root, "404.html");
  res.writeHead(404, { "Content-Type": TYPES[".html"] });
  if (!existsSync(page)) return res.end();
  createReadStream(page).pipe(res);
}

createServer((req, res) => {
  if (req.method === "HEAD") {
    res.writeHead(405, { Allow: "GET" });
    return res.end();
  }
  const url = new URL(req.url ?? "/", "http://localhost");
  let path = decodeURIComponent(url.pathname);
  if (path.startsWith("/mock-api/")) return mockApi(req, res, path.slice("/mock-api".length));
  if (req.method !== "GET") {
    res.writeHead(405, { Allow: "GET" });
    return res.end();
  }
  if (base) {
    if (path === "/" || path === base) {
      res.writeHead(301, { Location: `${base}/` });
      return res.end();
    }
    if (!path.startsWith(`${base}/`)) return send404(res);
    path = path.slice(base.length);
  }
  let file = normalize(join(root, path));
  if (file !== root && !file.startsWith(root + sep)) return send404(res);
  if (existsSync(file) && statSync(file).isDirectory()) {
    if (!url.pathname.endsWith("/")) {
      res.writeHead(301, { Location: `${url.pathname}/${url.search}` });
      return res.end();
    }
    file = join(file, "index.html");
  }
  if (!existsSync(file) && existsSync(`${file}.html`)) file = `${file}.html`;
  if (!existsSync(file) || !statSync(file).isFile()) return send404(res);
  const size = statSync(file).size;
  const headers = { "Content-Type": TYPES[extname(file)] ?? "application/octet-stream", "Accept-Ranges": "bytes", "Cache-Control": "no-cache" };
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  if (range && (range[1] || range[2])) {
    let start = range[1] ? Number(range[1]) : Math.max(size - Number(range[2]), 0);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start >= size || start > end) {
      res.writeHead(416, { ...headers, "Content-Range": `bytes */${size}` });
      return res.end();
    }
    start = Math.max(start, 0);
    res.writeHead(206, { ...headers, "Content-Range": `bytes ${start}-${end}/${size}`, "Content-Length": end - start + 1 });
    return createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...headers, "Content-Length": size });
  createReadStream(file).pipe(res);
}).listen(port, "127.0.0.1", () => {
  console.log(`serving out/ at http://127.0.0.1:${port}${base}/ (HEAD refused, the first /mock-api request answers 503)`);
});
