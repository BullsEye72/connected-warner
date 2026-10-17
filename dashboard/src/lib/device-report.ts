export const DEVICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const DEVICE_TOKEN = /^cw_[A-Za-z0-9_-]{43}$/;
export const MAX_REPORT_BYTES = 2048;

export type DeviceReport = {
  session: string;
  sequence: number;
  state: "repos" | "en_attente" | "confirmee" | "annulee";
  uptime_seconds: number;
  firmware_version: string;
  micropython_version: string;
  wifi_rssi?: number | null;
  request_id?: string | null;
  pushbullet_error?: "quota_mensuel" | null;
};

export function validReport(value: unknown): value is DeviceReport {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  const allowed = ["session", "sequence", "state", "uptime_seconds", "firmware_version", "micropython_version", "wifi_rssi", "request_id", "pushbullet_error"];
  const integer = (n: unknown, min: number, max: number) => typeof n === "number" && Number.isInteger(n) && n >= min && n <= max;
  const version = (s: unknown) => typeof s === "string" && s.length >= 1 && s.length <= 64;
  return Object.keys(r).every(key => allowed.includes(key)) &&
    typeof r.session === "string" && /^[0-9a-f]{24}$/.test(r.session) &&
    integer(r.sequence, 1, 2147483647) &&
    typeof r.state === "string" && ["repos", "en_attente", "confirmee", "annulee"].includes(r.state) &&
    integer(r.uptime_seconds, 0, 4294967295) && version(r.firmware_version) && version(r.micropython_version) &&
    (r.wifi_rssi == null || integer(r.wifi_rssi, -127, -1)) &&
    (r.request_id == null || typeof r.request_id === "string" && r.request_id.length <= 64) &&
    (r.pushbullet_error == null || r.pushbullet_error === "quota_mensuel");
}

export async function readReport(request: Request): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid");
  let text = "";
  let bytes = 0;
  const decoder = new TextDecoder("utf-8", { fatal: true });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_REPORT_BYTES) { await reader.cancel(); throw new Error("too_large"); }
      text += decoder.decode(value, { stream: true });
    }
    return JSON.parse(text + decoder.decode());
  } finally { reader.releaseLock(); }
}
