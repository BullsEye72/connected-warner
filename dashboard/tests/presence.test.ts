import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { PGlite } from "@electric-sql/pglite";
import { validReport, readReport, type DeviceReport } from "../src/lib/device-report.ts";

const db = new PGlite();
const alice = "11111111-1111-4111-8111-111111111111";
const bob = "22222222-2222-4222-8222-222222222222";
const device = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const token = "cw_" + "A".repeat(43);
const other = "cw_" + "B".repeat(43);
const report: DeviceReport = { session: "a".repeat(24), sequence: 1, state: "repos", uptime_seconds: 120,
  firmware_version: "test", micropython_version: "1.29.0", wifi_rssi: -60, request_id: null };
const hash = (value: string) => createHash("sha256").update(value).digest("hex");

async function asUser(id: string) {
  await db.exec("reset role; set role authenticated;");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [id]);
}
async function ingest(value: unknown, key = token, id = device) {
  await db.exec("reset role; set role anon;");
  const result = await db.query<{ status: { status: string } }>("select public.ingest_device_report($1,$2,$3::jsonb) as status", [id, key, JSON.stringify(value)]);
  return result.rows[0].status.status;
}
async function ageReceipt() {
  await db.exec("reset role; update warner_private.device_keys set received_at=clock_timestamp()-interval '3 seconds';");
}

before(async () => {
  await db.exec(`
    create role anon; create role authenticated; create role service_role bypassrls;
    create schema auth; create table auth.users(id uuid primary key, email text, created_at timestamptz default now());
    create function auth.uid() returns uuid language sql stable as
      $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
    grant usage on schema auth to anon,authenticated;
    grant execute on function auth.uid() to anon,authenticated;
    insert into auth.users(id) values ('${alice}'),('${bob}');
  `);
  for (const name of ["202610160001_dashboard.sql", "202610160002_device_presence.sql"]) {
    await db.exec(await readFile(new URL("../supabase/migrations/" + name, import.meta.url), "utf8"));
  }
  await db.query("insert into public.households(id,owner_id,name) values ($1,$2,'Home')", [device, alice]);
  await db.query("insert into public.devices(id,household_id,name) values ($1,$1,'Device')", [device]);
  await db.exec(await readFile(new URL("../supabase/migrations/202610160003_single_household_access.sql", import.meta.url), "utf8"));
  await db.exec(await readFile(new URL("../supabase/migrations/202610180004_pushbullet_error.sql", import.meta.url), "utf8"));
});
after(async () => { await db.close(); });

test("only the owner may provision a key; private hashes remain inaccessible", async () => {
  await asUser(bob);
  await assert.rejects(db.query("select public.set_device_key($1,$2)", [device, hash(token)]), /Device not accessible/);
  await asUser(alice);
  await db.query("select public.set_device_key($1,$2)", [device, hash(token)]);
  await assert.rejects(db.query("select * from warner_private.device_keys"), /permission denied/);
  await db.exec("reset role; set role anon;");
  await assert.rejects(db.query("select public.set_device_key($1,$2)", [device, hash(other)]), /permission denied/);
  await assert.rejects(db.query("select * from warner_private.device_sessions"), /permission denied/);
});

test("invalid key and cross-device report cannot update presence", async () => {
  assert.equal(await ingest(report, other), "unauthorized");
  assert.equal(await ingest(report, token, bob), "unauthorized");
  await asUser(alice);
  assert.equal((await db.query<{ last_seen_at: string | null }>("select last_seen_at from public.devices")).rows[0].last_seen_at, null);
});

test("first report is server-dated and duplicates cannot refresh presence or history", async () => {
  assert.equal(await ingest(report), "accepted");
  await asUser(alice);
  const first = (await db.query<{ last_seen_at: string; reboot_count: number }>("select last_seen_at,reboot_count from public.devices")).rows[0];
  assert.ok(Math.abs(Date.parse(first.last_seen_at) - Date.now()) < 10000);
  assert.equal(first.reboot_count, 0);
  assert.equal(await ingest(report), "obsolete");
  await asUser(alice);
  assert.deepEqual((await db.query<{ last_seen_at: string }>("select last_seen_at from public.devices")).rows[0].last_seen_at, first.last_seen_at);
  assert.equal((await db.query("select * from public.device_events")).rows.length, 1);
});

test("rate limiting and ordering prevent replay and duplicate events", async () => {
  const next = { ...report, sequence: 2, state: "en_attente", request_id: "test-request" };
  assert.equal(await ingest(next), "rate_limited");
  await ageReceipt();
  assert.equal(await ingest(next), "accepted");
  assert.equal(await ingest(report), "obsolete");
  assert.equal(await ingest(next), "obsolete");
  await asUser(alice);
  assert.equal((await db.query<{ count: number }>("select count(*)::int as count from public.device_events where event_type='aide'")).rows[0].count, 1);
});

test("an old boot cannot replace a more recent boot", async () => {
  await ageReceipt();
  assert.equal(await ingest({ ...report, session: "b".repeat(24) }), "accepted");
  assert.equal(await ingest({ ...report, sequence: 999 }), "obsolete");
  await asUser(alice);
  assert.equal((await db.query<{ reboot_count: number }>("select reboot_count from public.devices")).rows[0].reboot_count, 1);
});

test("a new request gets a new event even when both requests are awaiting confirmation", async () => {
  await ageReceipt();
  assert.equal(await ingest({ ...report, session: "b".repeat(24), sequence: 2, state: "en_attente", request_id: "first" }), "accepted");
  await ageReceipt();
  assert.equal(await ingest({ ...report, session: "b".repeat(24), sequence: 3, state: "en_attente", request_id: "second" }), "accepted");
  await asUser(alice);
  const rows = (await db.query<{ request_id: string }>("select request_id from public.device_events where event_type='aide' order by id")).rows;
  assert.deepEqual(rows.map(row => row.request_id), ["test-request", "first", "second"]);
});

test("rotation revokes the old key immediately", async () => {
  await asUser(alice);
  await db.query("select public.set_device_key($1,$2)", [device, hash(other)]);
  assert.equal(await ingest({ ...report, sequence: 1000 }), "unauthorized");
  assert.equal(await ingest(report, other), "accepted");
});

test("both API and direct RPC reject malformed telemetry and unknown fields", async () => {
  for (const invalid of [null, [], {}, { ...report, sequence: -1 }, { ...report, state: ["repos"] },
    { ...report, wifi_rssi: -200 }, { ...report, sequence: 2147483648 }, { ...report, uptime_seconds: 4294967296 },
    { ...report, firmware_version: "" }, { ...report, JETON_PUSHBULLET: "must-never-be-sent" }]) {
    assert.equal(validReport(invalid), false);
    assert.equal(await ingest(invalid, other), "invalid");
  }
  assert.equal(validReport(report), true);
});

test("request parser bounds streamed bodies even without Content-Length", async () => {
  const request = (body: string) => new Request("https://example.invalid", { method: "POST", body });
  assert.deepEqual(await readReport(request(JSON.stringify(report))), report);
  await assert.rejects(readReport(request("x".repeat(2049))), /too_large/);
  await assert.rejects(readReport(request("{invalid")), SyntaxError);
});

test("quota is retained across reports and reboots, cleared explicitly, and not duplicated in history", async () => {
  const warning = { ...report, session: "c".repeat(24), state: "confirmee", pushbullet_error: "quota_mensuel" };
  await ageReceipt();
  assert.equal(await ingest(warning, other), "accepted");
  await asUser(alice);
  const value = (await db.query<{ last_error: string; request_state: string }>("select last_error,request_state from public.devices")).rows[0];
  assert.equal(value.last_error, "pushbullet_quota_mensuel");
  assert.equal(value.request_state, "confirmee");
  assert.equal(await ingest(warning, other), "obsolete");
  await ageReceipt();
  assert.equal(await ingest({ ...warning, sequence: 2 }, other), "accepted");
  await asUser(alice);
  assert.equal((await db.query<{ count: number }>("select count(*)::int as count from public.device_events where event_type='erreur'")).rows[0].count, 1);
  for (const r of [{ ...report, session: "c".repeat(24), sequence: 3 }, { ...report, session: "d".repeat(24) }]) {
    await ageReceipt();
    assert.equal(await ingest(r, other), "accepted");
    await asUser(alice);
    assert.equal((await db.query<{ last_error: string }>("select last_error from public.devices")).rows[0].last_error, "pushbullet_quota_mensuel");
  }
  await ageReceipt();
  assert.equal(await ingest({ ...report, session: "d".repeat(24), sequence: 2, pushbullet_error: null }, other), "accepted");
  await asUser(alice);
  assert.equal((await db.query<{ last_error: string | null }>("select last_error from public.devices")).rows[0].last_error, null);
});

test("only the fixed quota code is accepted by both API and direct RPC", async () => {
  assert.equal(validReport({ ...report, pushbullet_error: "quota_mensuel" }), true);
  assert.equal(validReport({ ...report, pushbullet_error: null }), true);
  for (const pushbullet_error of ["secret@example.test", "", false, 1, [], {}, ["quota_mensuel"]]) {
    const r = { ...report, pushbullet_error };
    assert.equal(validReport(r), false);
    assert.equal(await ingest(r, other), "invalid");
  }
});
