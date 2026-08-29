const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const ALLOWED_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT"];
const POOL = 50;
const TIMEOUT = 4000;
const RETRY_TIMEOUT = 4500;
const MAX_SERVERS = 200;

function clean(host) {
  return host
    .trim()
    .toLowerCase()
    .replace(/^[a-z]+:\/\//, "")
    .split("/")[0]
    .split("?")[0]
    .replace(/\.$/, "");
}

function norm(type, answers) {
  switch (type) {
    case "MX":
      return answers.map((a) => `${a.priority} ${a.exchange}`);
    case "TXT":
      return answers.map((a) => (Array.isArray(a) ? a.join("") : String(a)));
    default:
      return answers.map(String);
  }
}

async function query(domain, type, ip, ms) {
  const start = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    const answers = await Deno.resolveDns(domain, type, {
      nameServer: { ipAddr: ip, port: 53 },
      signal: controller.signal,
      timeout: ms,
    });
    const arr = Array.isArray(answers) ? answers : [answers];
    return {
      ip,
      ok: true,
      resolveable: true,
      answers: norm(type, arr),
      ms: Math.round(performance.now() - start),
    };
  } catch (e) {
    const msg = String(e);
    const timedOut = /timed out|TimedOut|operation canceled|abort|AbortError/i.test(msg);
    const negative = timedOut ? false : /no records found|NotFound|Not Found|NXDOMAIN/i.test(msg);
    return {
      ip,
      ok: false,
      resolveable: negative ? false : null,
      timedOut,
      answers: [],
      ms: Math.round(performance.now() - start),
      error: msg,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function pool(servers, domain, type, ms) {
  const out = [];
  let i = 0;
  async function worker() {
    while (i < servers.length) {
      const idx = i++;
      try {
        out.push(await query(domain, type, servers[idx], ms));
      } catch (e) {
        out.push({ ip: servers[idx], ok: false, resolveable: null, timedOut: false, answers: [], ms: 0, error: String(e) });
      }
    }
  }
  const workers = Array.from({ length: Math.min(POOL, servers.length) }, worker);
  await Promise.all(workers);
  return out;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method Not Allowed" }), {
      status: 405,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }
  try {
    const body = await req.json().catch(() => null);
    if (!body) throw new Error("Invalid JSON body");
    const domain = clean(String(body.domain || ""));
    const type = String(body.type || "A").toUpperCase();
    if (!domain.includes(".") || domain.length > 253) throw new Error("Missing or invalid domain");
    if (!ALLOWED_TYPES.includes(type)) throw new Error(`Unsupported record type: ${type}`);
    const servers = Array.isArray(body.servers)
      ? body.servers.filter((s) => typeof s === "string" && s.includes("."))
      : [];
    if (servers.length === 0) throw new Error("No valid servers provided");
    const slice = servers.slice(0, MAX_SERVERS);
    const results = await pool(slice, domain, type, TIMEOUT);
    const retryIps = results.filter((r) => r.timedOut).map((r) => r.ip);
    if (retryIps.length > 0) {
      const retried = await pool(retryIps, domain, type, RETRY_TIMEOUT);
      const retriedMap = new Map(retried.map((r) => [r.ip, r]));
      for (const r of results) {
        const rr = retriedMap.get(r.ip);
        if (rr && !rr.timedOut) Object.assign(r, rr);
      }
    }
    return new Response(JSON.stringify({ domain, type, servers: results.length, results }), {
      headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 400,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }
});
