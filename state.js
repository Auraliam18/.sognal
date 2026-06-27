/* Hamid Signal Agent — cloud state API (Path B)
   GET  /api/state?key=YOURKEY     -> { data: <snapshot|null> }
   PUT  /api/state?key=YOURKEY     -> body { data: <snapshot> }  -> { ok: true }

   Storage: Upstash Redis REST (this is what Vercel KV / the Upstash
   integration provisions). Reads two environment variables that Vercel
   injects automatically when you add the store to the project:
     KV_REST_API_URL
     KV_REST_API_TOKEN
   (If your integration named them UPSTASH_REDIS_REST_URL / _TOKEN,
   those are accepted as a fallback too.)
*/

const REST_URL =
  process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "";
const REST_TOKEN =
  process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, PUT, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Cache-Control", "no-store");
}

function cleanKey(k) {
  return String(k || "")
    .trim()
    .replace(/[^A-Za-z0-9_-]/g, "")
    .slice(0, 64);
}

async function redisGet(redisKey) {
  const r = await fetch(`${REST_URL}/get/${encodeURIComponent(redisKey)}`, {
    headers: { Authorization: `Bearer ${REST_TOKEN}` },
  });
  if (!r.ok) throw new Error("redis get " + r.status);
  const j = await r.json();
  return j && typeof j.result === "string" ? j.result : null;
}

async function redisSet(redisKey, value) {
  const r = await fetch(`${REST_URL}/set/${encodeURIComponent(redisKey)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${REST_TOKEN}` },
    body: value,
  });
  if (!r.ok) throw new Error("redis set " + r.status);
  return true;
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  if (!REST_URL || !REST_TOKEN) {
    res.status(500).json({
      error:
        "Storage not configured. Add a KV / Upstash Redis store to this Vercel project so KV_REST_API_URL and KV_REST_API_TOKEN are set.",
    });
    return;
  }

  const key = cleanKey((req.query && req.query.key) || "");
  if (!key) {
    res.status(400).json({ error: "Missing or invalid ?key=" });
    return;
  }
  const redisKey = "hsa:state:" + key;

  try {
    if (req.method === "GET") {
      const raw = await redisGet(redisKey);
      let data = null;
      if (raw) {
        try { data = JSON.parse(raw); } catch (_) { data = null; }
      }
      res.status(200).json({ data });
      return;
    }

    if (req.method === "PUT" || req.method === "POST") {
      let body = req.body;
      if (typeof body === "string") {
        try { body = JSON.parse(body); } catch (_) { body = {}; }
      }
      const data = body && body.data !== undefined ? body.data : null;
      if (data === null) {
        res.status(400).json({ error: "Body must be { data: ... }" });
        return;
      }
      const payload = JSON.stringify(data);
      if (payload.length > 4_500_000) {
        res.status(413).json({ error: "Snapshot too large" });
        return;
      }
      await redisSet(redisKey, payload);
      res.status(200).json({ ok: true });
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
