import assert from "node:assert/strict";
import { test } from "node:test";
import { getPresence, formatSeen, displayDevice, needsAttention } from "../src/lib/device-status.ts";
import type { Device } from "../src/lib/supabase/database.types.ts";
import { parseSupabaseConfig } from "../src/lib/supabase/config.ts";

test("presence boundaries distinguish recent, delayed, absent and unseen devices", () => {
  const now = Date.UTC(2026, 9, 16, 12);
  const ago = (ms: number) => new Date(now - ms).toISOString();
  assert.equal(getPresence(null, now), "never");
  assert.equal(getPresence(ago(15 * 60_000), now), "recent");
  assert.equal(getPresence(ago(15 * 60_000 + 1), now), "late");
  assert.equal(getPresence(ago(30 * 60_000), now), "late");
  assert.equal(getPresence(ago(30 * 60_000 + 1), now), "offline");
  assert.equal(getPresence("invalid", now), "offline");
  assert.equal(getPresence(ago(-1), now), "offline");
  assert.match(formatSeen(ago(22 * 60_000), now), /22 min/);
});

test("public configuration accepts publishable/anon keys and rejects privileged keys", () => {
  const url = "https://example.supabase.co";
  const jwt = (role: string) => `header.${Buffer.from(JSON.stringify({ role })).toString("base64url")}.signature`;
  assert.ok(parseSupabaseConfig(url, "sb_publishable_test"));
  assert.ok(parseSupabaseConfig(url, jwt("anon")));
  assert.equal(parseSupabaseConfig(url, jwt("service_role")), null);
  assert.equal(parseSupabaseConfig(url, "sb_secret_test"), null);
  assert.equal(parseSupabaseConfig(url, "invalid"), null);
  assert.equal(parseSupabaseConfig(undefined, "sb_publishable_test"), null);
  assert.equal(parseSupabaseConfig("http://example.com", "sb_publishable_test"), null);
  assert.ok(parseSupabaseConfig("http://127.0.0.1:54321", "sb_publishable_test"));
});

test("a recent device with quota warning needs attention without changing its confirmed state", () => {
  const now = Date.UTC(2026, 9, 18, 12);
  const device: Device = { id: "test", household_id: "home", name: "Lit", location: "Chambre",
    created_at: new Date(now).toISOString(), last_seen_at: new Date(now).toISOString(),
    request_state: "confirmee", request_id: "req", firmware_version: "test", micropython_version: "1.29",
    wifi_rssi: -60, uptime_seconds: 120, reboot_count: 0, last_error: "pushbullet_quota_mensuel" };
  const warning = displayDevice(device, now);
  assert.equal(warning.presence, "recent");
  assert.equal(warning.stateKind, "confirmee");
  assert.match(warning.lastError!, /Quota mensuel Pushbullet atteint/);
  assert.equal(needsAttention(warning), true);
  const healthy = displayDevice({ ...device, last_error: null }, now);
  assert.equal(needsAttention(healthy), false);
  const offlineWarning = displayDevice({ ...device, last_seen_at: new Date(now - 31 * 60_000).toISOString() }, now);
  assert.equal([warning, healthy, offlineWarning].filter(needsAttention).length, 2);
});
