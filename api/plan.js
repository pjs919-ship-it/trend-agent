const ALLOWED_MODELS = new Set([
  "gemini-2.5-flash-lite",
  "gemini-flash-latest"
]);

module.exports = async function handler(req, res) {
  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method Not Allowed" });
  }

  const apiKey = (process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || "").trim();
  if (!apiKey) {
    return res.status(503).json({ error: "SERVER_API_KEY_NOT_CONFIGURED" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      return res.status(400).json({ error: "INVALID_JSON" });
    }
  }

  const prompt = typeof body?.prompt === "string" ? body.prompt.trim() : "";
  if (!prompt || prompt.length > 16000) {
    return res.status(400).json({ error: "INVALID_PROMPT" });
  }

  const rawModel = typeof body?.model === "string" ? body.model.trim() : "";
  const model = ALLOWED_MODELS.has(rawModel) ? rawModel : "gemini-2.5-flash-lite";

  try {
    const upstream = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": apiKey
        },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.25,
            responseMimeType: "application/json"
          }
        })
      }
    );

    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return res.status(upstream.status).json({
        error: "UPSTREAM_AI_ERROR",
        status: upstream.status,
        detail: data?.error?.message ? String(data.error.message).slice(0, 180) : ""
      });
    }

    const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
    let parsed = {};
    try {
      parsed = JSON.parse(rawText);
    } catch {
      return res.status(502).json({ error: "INVALID_AI_JSON" });
    }

    return res.status(200).json({ plan: parsed });
  } catch {
    return res.status(502).json({ error: "UPSTREAM_FETCH_FAILED" });
  }
};
