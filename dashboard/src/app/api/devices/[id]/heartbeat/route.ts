import { DEVICE_ID, DEVICE_TOKEN, readReport, validReport } from "@/lib/device-report";
import { createIngestionClient } from "@/lib/supabase/ingestion";

export const runtime = "nodejs";

function response(status: number, value: object, retry?: string) {
  return Response.json(value, { status, headers: { "Cache-Control": "no-store", ...(retry ? { "Retry-After": retry } : {}) } });
}

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (!DEVICE_ID.test(id) || !DEVICE_TOKEN.test(token)) return response(401, { error: "unauthorized" });
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") return response(415, { error: "content_type" });
  let report: unknown;
  try { report = await readReport(request); } catch (error) {
    return response(error instanceof Error && error.message === "too_large" ? 413 : 400, { error: "invalid_report" });
  }
  if (!validReport(report)) return response(400, { error: "invalid_report" });
  const client = createIngestionClient();
  if (!client) return response(503, { error: "unavailable" }, "60");
  // Ne journaliser ni l'Authorization, ni le corps, ni les erreurs brutes Supabase.
  const { data, error } = await client.rpc("ingest_device_report", { p_device_id: id, p_token: token, p_report: report });
  if (error || !data) return response(503, { error: "unavailable" }, "60");
  if (data.status === "unauthorized") return response(401, { error: "unauthorized" });
  if (data.status === "invalid") return response(400, { error: "invalid_report" });
  if (data.status === "rate_limited") return response(429, { error: "rate_limited" }, "2");
  if (data.status === "obsolete") return response(200, { accepted: false });
  if (data.status !== "accepted") return response(503, { error: "unavailable" }, "60");
  return response(200, { accepted: true });
}
