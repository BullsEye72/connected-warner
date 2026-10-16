import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

const db = new PGlite();
const alice = "11111111-1111-4111-8111-111111111111";
const bob = "22222222-2222-4222-8222-222222222222";
let household: string;
let device: string;

async function asUser(id: string) {
  await db.exec("reset role; set role authenticated;");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [id]);
}

before(async () => {
  await db.exec(`
    create role anon;
    create role authenticated;
    create role service_role bypassrls;
    create schema auth;
    create table auth.users (id uuid primary key);
    create function auth.uid() returns uuid language sql stable as
      $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
    grant usage on schema auth to anon, authenticated;
    grant execute on function auth.uid() to anon, authenticated;
    insert into auth.users values ('${alice}'), ('${bob}');
  `);
  const migration = await readFile(new URL("../supabase/migrations/202610160001_dashboard.sql", import.meta.url), "utf8");
  await db.exec(migration);
  await db.exec(await readFile(new URL("../supabase/migrations/202610160002_device_presence.sql", import.meta.url), "utf8"));
  await asUser(alice);
  const result = await db.query<{ id: string }>("insert into public.households(owner_id,name) values ($1,'Chez Alice') returning id", [alice]);
  household = result.rows[0].id;
  const created = await db.query<{ id: string }>("insert into public.devices(household_id,name,location) values ($1,'Lit','Chambre') returning id", [household]);
  device = created.rows[0].id;
  await db.exec("reset role;");
  await db.query("insert into public.device_events(device_id,event_type) values ($1,'demarrage')", [device]);
});

after(async () => { await db.close(); });

test("anonymous clients cannot read private tables", async () => {
  await db.exec("reset role; set role anon;");
  for (const table of ["households", "devices", "device_events"]) {
    await assert.rejects(db.query(`select * from public.${table}`), /permission denied/);
  }
});

test("an owner can read their household, device and event", async () => {
  await asUser(alice);
  for (const table of ["households", "devices", "device_events"]) {
    const result = await db.query(`select * from public.${table}`);
    assert.equal(result.rows.length, 1);
  }
});

test("another account cannot read or change Alice's data", async () => {
  await asUser(bob);
  for (const table of ["households", "devices", "device_events"]) {
    assert.equal((await db.query(`select * from public.${table}`)).rows.length, 0);
  }
  assert.equal((await db.query("update public.devices set name='Changed' where id=$1 returning id", [device])).rows.length, 0);
  await assert.rejects(db.query("insert into public.devices(household_id,name) values ($1,'Intruder')", [household]), /row-level security/);
  await assert.rejects(db.query("insert into public.households(owner_id,name) values ($1,'Intruder')", [alice]), /row-level security/);
});

test("owners can edit labels but cannot fabricate telemetry or events", async () => {
  await asUser(alice);
  await db.query("update public.devices set name='Lit principal' where id=$1", [device]);
  assert.equal((await db.query<{ name: string }>("select name from public.devices where id=$1", [device])).rows[0].name, "Lit principal");
  await assert.rejects(db.query("update public.devices set last_seen_at=now() where id=$1", [device]), /permission denied/);
  await assert.rejects(db.query("update public.devices set request_state='confirmee' where id=$1", [device]), /permission denied/);
  await assert.rejects(db.query("insert into public.devices(household_id,name,last_seen_at) values ($1,'Fake',now())", [household]), /permission denied/);
  await assert.rejects(db.query("insert into public.device_events(device_id,event_type) values ($1,'confirmation')", [device]), /permission denied/);
  await assert.rejects(db.query("update public.households set owner_id=$1 where id=$2", [bob, household]), /permission denied/);
});

test("new devices remain unseen and cannot be moved into another household", async () => {
  await asUser(bob);
  const result = await db.query<{ id: string }>("insert into public.households(owner_id,name) values ($1,'Chez Bob') returning id", [bob]);
  const bobHome = result.rows[0].id;
  await asUser(alice);
  const row = (await db.query<{ last_seen_at: string | null; request_state: string }>("select last_seen_at,request_state from public.devices where id=$1", [device])).rows[0];
  assert.equal(row.last_seen_at, null);
  assert.equal(row.request_state, "inconnu");
  await assert.rejects(db.query("update public.devices set household_id=$1 where id=$2", [bobHome, device]), /permission denied/);
});
