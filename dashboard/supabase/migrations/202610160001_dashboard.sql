-- A executer une fois dans le SQL Editor Supabase (ou via supabase db push).
-- Les comptes Google sont geres dans auth.users par Supabase Auth.
begin;

create table public.households (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null unique references auth.users(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 80),
  created_at timestamptz not null default now()
);

create table public.devices (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 40),
  location text not null default '' check (char_length(location) <= 80),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz,
  request_state text not null default 'inconnu'
    check (request_state in ('inconnu', 'repos', 'en_attente', 'confirmee', 'annulee')),
  firmware_version text,
  micropython_version text,
  wifi_rssi integer check (wifi_rssi between -127 and 0),
  uptime_seconds bigint check (uptime_seconds >= 0),
  reboot_count integer check (reboot_count >= 0),
  last_error text
);
create index devices_household_id_idx on public.devices(household_id);

create table public.device_events (
  id bigint generated always as identity primary key,
  device_id uuid not null references public.devices(id) on delete cascade,
  event_type text not null check (event_type in
    ('demarrage', 'aide', 'confirmation', 'annulation', 'erreur', 'mise_a_jour')),
  received_at timestamptz not null default now(),
  request_id text
);
create index device_events_device_received_idx on public.device_events(device_id, received_at desc);

alter table public.households enable row level security;
alter table public.devices enable row level security;
alter table public.device_events enable row level security;

create policy households_select on public.households for select to authenticated
  using (owner_id = (select auth.uid()));
create policy households_insert on public.households for insert to authenticated
  with check (owner_id = (select auth.uid()));
create policy households_update on public.households for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));

create policy devices_select on public.devices for select to authenticated using (
  exists (select 1 from public.households h where h.id = household_id and h.owner_id = (select auth.uid()))
);
create policy devices_insert on public.devices for insert to authenticated with check (
  exists (select 1 from public.households h where h.id = household_id and h.owner_id = (select auth.uid()))
);
create policy devices_update on public.devices for update to authenticated using (
  exists (select 1 from public.households h where h.id = household_id and h.owner_id = (select auth.uid()))
) with check (
  exists (select 1 from public.households h where h.id = household_id and h.owner_id = (select auth.uid()))
);
create policy events_select on public.device_events for select to authenticated using (
  exists (select 1 from public.devices d join public.households h on h.id = d.household_id
    where d.id = device_id and h.owner_id = (select auth.uid()))
);

-- Aucun acces anonyme. Les utilisateurs peuvent nommer les boitiers mais ne
-- peuvent pas fabriquer une presence, une confirmation ou un evenement.
revoke all on public.households, public.devices, public.device_events from public, anon, authenticated;
revoke all on sequence public.device_events_id_seq from public, anon, authenticated;
grant select on public.households, public.devices, public.device_events to authenticated;
grant insert (owner_id, name) on public.households to authenticated;
grant update (name) on public.households to authenticated;
grant insert (household_id, name, location) on public.devices to authenticated;
grant update (name, location) on public.devices to authenticated;
-- Reserve a la future API serveur authentifiant chaque carte.
grant all on public.households, public.devices, public.device_events to service_role;
grant usage, select on sequence public.device_events_id_seq to service_role;

commit;
