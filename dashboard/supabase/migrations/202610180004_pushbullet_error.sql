-- Apres les trois migrations precedentes. Conserve boitiers, cles et historiques.
begin;
create or replace function public.ingest_device_report(p_device_id uuid, p_token text, p_report jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  credentials warner_private.device_keys%rowtype;
  previous public.devices%rowtype;
  stamp timestamptz := clock_timestamp();
  session_id text;
  seq bigint;
  new_state text;
  new_boot boolean;
  event_name text;
  new_error text;
begin
  if p_token is null or p_token !~ '^cw_[A-Za-z0-9_-]{43}$' then
    return jsonb_build_object('status', 'unauthorized');
  end if;
  select * into credentials from warner_private.device_keys where device_id = p_device_id for update;
  if not found or credentials.token_hash <> encode(sha256(convert_to(p_token, 'UTF8')), 'hex') then
    return jsonb_build_object('status', 'unauthorized');
  end if;
  if p_report is null or jsonb_typeof(p_report) <> 'object' or
     p_report - array['session','sequence','state','uptime_seconds','firmware_version','micropython_version','wifi_rssi','request_id','pushbullet_error'] <> '{}'::jsonb or
     jsonb_typeof(p_report->'session') is distinct from 'string' or
     (p_report->>'session') !~ '^[0-9a-f]{24}$' or
     jsonb_typeof(p_report->'sequence') is distinct from 'number' or
     (p_report->>'sequence') !~ '^[1-9][0-9]{0,9}$' or
     jsonb_typeof(p_report->'state') is distinct from 'string' or
     (p_report->>'state') not in ('repos','en_attente','confirmee','annulee') or
     jsonb_typeof(p_report->'uptime_seconds') is distinct from 'number' or
     (p_report->>'uptime_seconds') !~ '^[0-9]{1,10}$' or
     jsonb_typeof(p_report->'firmware_version') is distinct from 'string' or
     char_length(p_report->>'firmware_version') not between 1 and 64 or
     jsonb_typeof(p_report->'micropython_version') is distinct from 'string' or
     char_length(p_report->>'micropython_version') not between 1 and 64 or
     (p_report ? 'wifi_rssi' and p_report->'wifi_rssi' <> 'null'::jsonb and
       (jsonb_typeof(p_report->'wifi_rssi') <> 'number' or (p_report->>'wifi_rssi') !~ '^-[0-9]{1,3}$')) or
     (p_report ? 'request_id' and p_report->'request_id' <> 'null'::jsonb and
       (jsonb_typeof(p_report->'request_id') <> 'string' or char_length(p_report->>'request_id') > 64)) or
     (p_report ? 'pushbullet_error' and p_report->'pushbullet_error' <> 'null'::jsonb and
       (jsonb_typeof(p_report->'pushbullet_error') <> 'string' or p_report->>'pushbullet_error' <> 'quota_mensuel'))
  then return jsonb_build_object('status', 'invalid'); end if;
  seq := (p_report->>'sequence')::bigint;
  if seq > 2147483647 or (p_report->>'uptime_seconds')::bigint > 4294967295 or
    (p_report->>'wifi_rssi')::integer not between -127 and -1
  then return jsonb_build_object('status', 'invalid'); end if;
  session_id := p_report->>'session';
  new_state := p_report->>'state';
  new_boot := credentials.current_session is distinct from session_id;
  if (not new_boot and seq <= credentials.last_sequence) or (new_boot and exists (
    select 1 from warner_private.device_sessions where device_id = p_device_id and session = session_id
  )) then return jsonb_build_object('status', 'obsolete'); end if;
  if credentials.received_at is not null and stamp - credentials.received_at < interval '2 seconds' then
    return jsonb_build_object('status', 'rate_limited');
  end if;
  select * into previous from public.devices where id = p_device_id for update;
  -- Un ancien firmware ou un redemarrage ne prouve pas la fin du probleme.
  -- Seul un rapport explicite peut remplacer/effacer le code deja signale.
  new_error := case when p_report ? 'pushbullet_error'
    then case when p_report->>'pushbullet_error' = 'quota_mensuel' then 'pushbullet_quota_mensuel' end
    else previous.last_error end;
  if new_boot then
    insert into warner_private.device_sessions values (p_device_id, session_id);
    insert into public.device_events(device_id, event_type) values (p_device_id, 'demarrage');
  end if;
  update public.devices set last_seen_at = stamp, request_state = new_state,
    request_id = p_report->>'request_id', last_error = new_error,
    firmware_version = p_report->>'firmware_version', micropython_version = p_report->>'micropython_version',
    wifi_rssi = (p_report->>'wifi_rssi')::integer, uptime_seconds = (p_report->>'uptime_seconds')::bigint,
    reboot_count = coalesce(previous.reboot_count, 0) + case when new_boot and credentials.current_session is not null then 1 else 0 end
    where id = p_device_id;
  if new_error is not null and new_error is distinct from previous.last_error then
    insert into public.device_events(device_id, event_type, request_id)
      values (p_device_id, 'erreur', p_report->>'request_id');
  end if;
  if previous.request_state is distinct from new_state or previous.request_id is distinct from (p_report->>'request_id') or new_boot then
    event_name := case new_state when 'en_attente' then 'aide' when 'confirmee' then 'confirmation' when 'annulee' then 'annulation' end;
    if event_name is not null then
      insert into public.device_events(device_id,event_type,request_id) values (p_device_id,event_name,p_report->>'request_id');
    end if;
  end if;
  update warner_private.device_keys set current_session = session_id, last_sequence = seq, received_at = stamp where device_id = p_device_id;
  return jsonb_build_object('status', 'accepted');
end;
$$;
revoke all on function public.ingest_device_report(uuid, text, jsonb) from public, anon, authenticated;
grant execute on function public.ingest_device_report(uuid, text, jsonb) to anon;
commit;
