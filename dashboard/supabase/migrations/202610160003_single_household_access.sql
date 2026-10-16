-- Executer apres 001 et 002. Une installation = un logement partage.
-- Le proprietaire du logement existant reste administrateur ; aucune cle ne change.
begin;

-- Serialise l'installation avec les inscriptions et les creations de logements.
lock table auth.users in share row exclusive mode;
lock table public.households in share row exclusive mode;
do $$ begin
  if (select count(*) from public.households) > 1 then
    raise exception 'Plusieurs logements existent : choisir et conserver un seul logement avant cette migration.';
  end if;
end $$;
create unique index households_single_instance on public.households ((true));

create table warner_private.instance (
  singleton boolean primary key default true check (singleton),
  admin_id uuid references auth.users(id) on delete restrict
);
alter table warner_private.instance enable row level security;
revoke all on warner_private.instance from public, anon, authenticated;
insert into warner_private.instance(singleton, admin_id)
values (true, coalesce(
  (select owner_id from public.households limit 1),
  (select id from auth.users order by created_at, id limit 1)
));

create table public.dashboard_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.dashboard_members enable row level security;
revoke all on public.dashboard_members from public, anon, authenticated;
grant select on public.dashboard_members to authenticated;
grant all on public.dashboard_members to service_role;
insert into public.dashboard_members(user_id, email, status, created_at)
select u.id, u.email, case when u.id = i.admin_id then 'approved' else 'pending' end,
  coalesce(u.created_at, now())
from auth.users u cross join warner_private.instance i;

-- Le verrou de la ligne singleton evite deux administrateurs au premier acces.
-- L'adresse provient d'auth.users, jamais de metadonnees modifiables par le client.
create function warner_private.register_dashboard_user()
returns trigger language plpgsql security definer set search_path = '' as $$
declare administrator uuid;
begin
  select admin_id into administrator from warner_private.instance where singleton for update;
  if administrator is null then
    update warner_private.instance set admin_id = new.id where singleton;
    administrator := new.id;
  end if;
  insert into public.dashboard_members(user_id, email, status)
    values (new.id, new.email, case when new.id = administrator then 'approved' else 'pending' end);
  return new;
end;
$$;
revoke all on function warner_private.register_dashboard_user() from public, anon, authenticated;
create trigger warner_dashboard_user_created after insert on auth.users
for each row execute function warner_private.register_dashboard_user();

create function public.is_dashboard_admin()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from warner_private.instance where admin_id = (select auth.uid()));
$$;
create function public.has_dashboard_access()
returns boolean language sql stable security definer set search_path = '' as $$
  select public.is_dashboard_admin() or exists (
    select 1 from public.dashboard_members where user_id = (select auth.uid()) and status = 'approved'
  );
$$;
revoke all on function public.is_dashboard_admin(), public.has_dashboard_access() from public, anon, authenticated;
grant execute on function public.is_dashboard_admin(), public.has_dashboard_access() to authenticated;

create policy members_select on public.dashboard_members for select to authenticated
using (user_id = (select auth.uid()) or (select public.is_dashboard_admin()));

create function public.set_dashboard_access(p_user_id uuid, p_status text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_dashboard_admin() then
    raise exception 'Administrator required' using errcode = '42501';
  end if;
  if p_user_id is null or p_user_id = (select auth.uid()) or
     p_status is null or p_status not in ('approved', 'rejected') then
    raise exception 'Invalid access change' using errcode = '22023';
  end if;
  update public.dashboard_members set status = p_status, updated_at = clock_timestamp()
    where user_id = p_user_id;
  if not found then raise exception 'Unknown account' using errcode = '22023'; end if;
end;
$$;
revoke all on function public.set_dashboard_access(uuid, text) from public, anon, authenticated;
grant execute on function public.set_dashboard_access(uuid, text) to authenticated;

create function public.create_shared_household(p_name text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_dashboard_admin() then
    raise exception 'Administrator required' using errcode = '42501';
  end if;
  if p_name is null or char_length(btrim(p_name)) not between 1 and 80 then
    raise exception 'Invalid household name' using errcode = '22023';
  end if;
  insert into public.households(owner_id, name) values ((select auth.uid()), btrim(p_name));
end;
$$;
revoke all on function public.create_shared_household(text) from public, anon, authenticated;
grant execute on function public.create_shared_household(text) to authenticated;

-- Les membres approuves lisent le meme logement ; seul l'admin le configure.
revoke insert on public.households from authenticated;
revoke insert (owner_id, name) on public.households from authenticated;
drop policy households_select on public.households;
drop policy households_insert on public.households;
drop policy households_update on public.households;
create policy households_select on public.households for select to authenticated
  using ((select public.has_dashboard_access()));
create policy households_update on public.households for update to authenticated
  using ((select public.is_dashboard_admin())) with check ((select public.is_dashboard_admin()));

drop policy devices_select on public.devices;
drop policy devices_insert on public.devices;
drop policy devices_update on public.devices;
create policy devices_select on public.devices for select to authenticated
  using ((select public.has_dashboard_access()));
create policy devices_insert on public.devices for insert to authenticated
  with check ((select public.is_dashboard_admin()));
create policy devices_update on public.devices for update to authenticated
  using ((select public.is_dashboard_admin())) with check ((select public.is_dashboard_admin()));

drop policy events_select on public.device_events;
create policy events_select on public.device_events for select to authenticated
  using ((select public.has_dashboard_access()));
-- set_device_key reste reserve au proprietaire, qui est l'admin de l'installation.
-- ingest_device_report reste independant des sessions et des approbations humaines.
commit;
