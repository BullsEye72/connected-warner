import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

const db = new PGlite();
const alice = "11111111-1111-4111-8111-111111111111";
const bob = "22222222-2222-4222-8222-222222222222";
const charlie = "33333333-3333-4333-8333-333333333333";
let household: string;
let device: string;
const migration = async (name: string) => readFile(new URL("../supabase/migrations/" + name, import.meta.url), "utf8");
const sharedMigration = "202610160003_single_household_access.sql";

async function init(database: PGlite) {
  await database.exec(`
    create role anon; create role authenticated; create role service_role bypassrls;
    create schema auth;
    create table auth.users(id uuid primary key, email text, created_at timestamptz default now());
    create function auth.uid() returns uuid language sql stable as
      $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
    grant usage on schema auth to anon, authenticated;
    grant execute on function auth.uid() to anon, authenticated;
  `);
  for (const name of ["202610160001_dashboard.sql", "202610160002_device_presence.sql"]) await database.exec(await migration(name));
}
async function asUser(id: string, database = db) {
  await database.exec("reset role; set role authenticated;");
  await database.query("select set_config('request.jwt.claim.sub', $1, false)", [id]);
}
async function decide(id: string, status: string) {
  await db.query("select public.set_dashboard_access($1,$2)", [id, status]);
}

before(async () => {
  await init(db);
  // Bob est plus ancien, mais Alice possede deja le logement deploye.
  await db.query("insert into auth.users(id,email,created_at) values ($1,'bob@example.test','2026-01-01'),($2,'alice@example.test','2026-02-01')", [bob, alice]);
  await asUser(alice);
  household = (await db.query<{ id: string }>("insert into public.households(owner_id,name) values ($1,'Chez Alice') returning id", [alice])).rows[0].id;
  device = (await db.query<{ id: string }>("insert into public.devices(household_id,name) values ($1,'Lit') returning id", [household])).rows[0].id;
  await db.query("select public.set_device_key($1,$2)", [device, "a".repeat(64)]);
  await db.exec("reset role;");
  await db.query("insert into public.device_events(device_id,event_type) values ($1,'demarrage')", [device]);
  await db.exec(await migration(sharedMigration));
  await db.exec(await migration("202610180004_pushbullet_error.sql"));
});
after(async () => { await db.close(); });

test("migration preserves the existing owner, household, devices and keys", async () => {
  await asUser(alice);
  assert.equal((await db.query<{ admin: boolean }>("select public.is_dashboard_admin() as admin")).rows[0].admin, true);
  for (const table of ["households", "devices", "device_events"]) assert.equal((await db.query(`select * from public.${table}`)).rows.length, 1);
  await db.exec("reset role;");
  assert.equal((await db.query<{ token_hash: string }>("select token_hash from warner_private.device_keys")).rows[0].token_hash, "a".repeat(64));
});

test("anonymous clients cannot read or administer the installation", async () => {
  await db.exec("reset role; set role anon;");
  for (const table of ["households", "devices", "device_events", "dashboard_members"]) await assert.rejects(db.query(`select * from public.${table}`), /permission denied/);
  for (const sql of ["select public.is_dashboard_admin()", "select public.has_dashboard_access()", "select public.create_shared_household('X')", `select public.set_dashboard_access('${bob}','approved')`]) await assert.rejects(db.query(sql), /permission denied/);
});

test("pending accounts see only their own request and no household data", async () => {
  await asUser(bob);
  for (const table of ["households", "devices", "device_events"]) assert.equal((await db.query(`select * from public.${table}`)).rows.length, 0);
  const rows = (await db.query<{ user_id: string; status: string }>("select * from public.dashboard_members")).rows;
  assert.equal(rows.length, 1); assert.equal(rows[0].user_id, bob); assert.equal(rows[0].status, "pending");
  await assert.rejects(db.query("select * from warner_private.instance"), /permission denied/);
});

test("pending accounts cannot self-approve, forge requests, claim ownership or change devices", async () => {
  await asUser(bob);
  await assert.rejects(decide(bob, "approved"), /Administrator required/);
  await assert.rejects(db.query("update public.dashboard_members set status='approved' where user_id=$1", [bob]), /permission denied/);
  await assert.rejects(db.query("insert into public.dashboard_members(user_id,status) values ($1,'approved')", [charlie]), /permission denied/);
  await assert.rejects(db.query("select public.create_shared_household('Intruder')"), /Administrator required/);
  await assert.rejects(db.query("insert into public.households(owner_id,name) values ($1,'Intruder')", [bob]), /permission denied/);
  await assert.rejects(db.query("insert into public.devices(household_id,name) values ($1,'Intruder')", [household]), /row-level security/);
  assert.equal((await db.query("update public.devices set name='Changed' returning id")).rows.length, 0);
});

test("approval shares the same household and history, with read-only access", async () => {
  await asUser(alice); await decide(bob, "approved");
  await asUser(bob);
  assert.equal((await db.query<{ id: string }>("select id from public.households")).rows[0].id, household);
  for (const table of ["devices", "device_events"]) assert.equal((await db.query(`select * from public.${table}`)).rows.length, 1);
  assert.equal((await db.query("update public.devices set name='Changed' returning id")).rows.length, 0);
  assert.equal((await db.query("update public.households set name='Changed' returning id")).rows.length, 0);
  await assert.rejects(db.query("insert into public.devices(household_id,name) values ($1,'Fake')", [household]), /row-level security/);
  await assert.rejects(db.query("select public.set_device_key($1,$2)", [device, "b".repeat(64)]), /Device not accessible/);
  await assert.rejects(decide(alice, "rejected"), /Administrator required/);
});

test("revocation applies to an existing session on its next database request", async () => {
  await asUser(alice); await decide(bob, "rejected");
  await asUser(bob); // Meme identite JWT, sans deconnexion ni nouveau jeton.
  for (const table of ["households", "devices", "device_events"]) assert.equal((await db.query(`select * from public.${table}`)).rows.length, 0);
  assert.equal((await db.query<{ status: string }>("select status from public.dashboard_members")).rows[0].status, "rejected");
});

test("new signups automatically enter the queue and the administrator sees all requests", async () => {
  await db.exec("reset role;");
  await db.query("insert into auth.users(id,email) values ($1,'charlie@example.test')", [charlie]);
  await asUser(charlie);
  assert.equal((await db.query<{ status: string }>("select status from public.dashboard_members")).rows[0].status, "pending");
  assert.equal((await db.query("select * from public.households")).rows.length, 0);
  await asUser(alice);
  assert.equal((await db.query("select * from public.dashboard_members")).rows.length, 3);
  await decide(charlie, "rejected"); await decide(charlie, "approved");
  await asUser(charlie);
  assert.equal((await db.query("select * from public.devices")).rows.length, 1);
});

test("signup trigger works for the auth service without access to application tables", async () => {
  await db.exec(`reset role; create role auth_test_service;
    grant usage on schema auth to auth_test_service;
    grant insert on auth.users to auth_test_service;
    set role auth_test_service;`);
  const id = "55555555-5555-4555-8555-555555555555";
  await db.query("insert into auth.users(id,email) values ($1,'signup@example.test')", [id]);
  await asUser(id);
  assert.equal((await db.query<{ status: string }>("select status from public.dashboard_members")).rows[0].status, "pending");
  await assert.rejects(db.query("select warner_private.register_dashboard_user()"), /permission denied/);
});

test("administrator cannot revoke themselves or create a second household", async () => {
  await asUser(alice);
  await assert.rejects(decide(alice, "rejected"), /Invalid access change/);
  await assert.rejects(decide(bob, "admin"), /Invalid access change/);
  await assert.rejects(decide("44444444-4444-4444-8444-444444444444", "approved"), /Unknown account/);
  await assert.rejects(db.query("select public.create_shared_household('Second')"), /duplicate key/);
  await assert.rejects(db.query("insert into public.households(owner_id,name) values ($1,'Second')", [alice]), /permission denied/);
});

test("administrator still manages labels and keys but cannot fabricate telemetry", async () => {
  await asUser(alice);
  await db.query("update public.devices set name='Lit principal' where id=$1", [device]);
  await db.query("select public.set_device_key($1,$2)", [device, "b".repeat(64)]);
  await assert.rejects(db.query("update public.devices set last_seen_at=now()"), /permission denied/);
  await assert.rejects(db.query("update public.devices set last_error='forged'"), /permission denied/);
  await assert.rejects(db.query("insert into public.device_events(device_id,event_type) values ($1,'confirmation')", [device]), /permission denied/);
  await assert.rejects(db.query("update public.households set owner_id=$1", [bob]), /permission denied/);
});

test("fresh installation assigns only the first signup as administrator", async () => {
  const fresh = new PGlite();
  try {
    await init(fresh); await fresh.exec(await migration(sharedMigration));
    await fresh.query("insert into auth.users(id,email) values ($1,'first@example.test'),($2,'second@example.test')", [alice, bob]);
    await asUser(bob, fresh);
    await assert.rejects(fresh.query("select public.create_shared_household('No')"), /Administrator required/);
    await asUser(alice, fresh);
    await fresh.query("select public.create_shared_household('Shared')");
    assert.equal((await fresh.query<{ owner_id: string }>("select owner_id from public.households")).rows[0].owner_id, alice);
  } finally { await fresh.close(); }
});

test("without an existing household the oldest account becomes administrator", async () => {
  const fresh = new PGlite();
  try {
    await init(fresh);
    await fresh.query("insert into auth.users(id,created_at) values ($1,'2026-02-01'),($2,'2026-01-01')", [alice, bob]);
    await fresh.exec(await migration(sharedMigration)); await asUser(bob, fresh);
    assert.equal((await fresh.query<{ admin: boolean }>("select public.is_dashboard_admin() as admin")).rows[0].admin, true);
  } finally { await fresh.close(); }
});

test("multiple existing households stop migration without deleting data", async () => {
  const fresh = new PGlite();
  try {
    await init(fresh);
    await fresh.query("insert into auth.users(id) values ($1),($2)", [alice, bob]);
    await fresh.query("insert into public.households(owner_id,name) values ($1,'A'),($2,'B')", [alice, bob]);
    await assert.rejects(fresh.exec(await migration(sharedMigration)), /Plusieurs logements existent/);
    await fresh.exec("rollback;");
    assert.equal((await fresh.query("select * from public.households")).rows.length, 2);
  } finally { await fresh.close(); }
});
