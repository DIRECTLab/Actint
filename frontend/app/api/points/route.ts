export async function POST(request: Request): Promise<Response> {
  const payload = await request.json();

  const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:5000").replace(/\/$/, "");

  const upstream = await fetch(`${backendUrl}/points`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const contentType = upstream.headers.get("content-type") ?? "application/json";
  const text = await upstream.text();

  return new Response(text, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}
