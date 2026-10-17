import type { Device } from "./supabase/database.types";

export type Presence = "recent" | "late" | "offline" | "never";
export type DisplayDevice = {
  id: string;
  name: string;
  location: string;
  presence: Presence;
  presenceLabel: string;
  tone: "green" | "amber" | "neutral";
  lastSeen: string;
  seenDate: string | null;
  state: string;
  stateKind: Device["request_state"];
  wifi: string;
  uptime: string;
  version: string;
  micropython: string;
  reboots: string;
  note: string;
  lastError: string | null;
};

const states: Record<Device["request_state"], string> = {
  inconnu: "Aucun état reçu",
  repos: "Au repos",
  en_attente: "Demande en attente",
  confirmee: "Aide confirmée",
  annulee: "Demande annulée",
};

export function getPresence(lastSeen: string | null, now: number): Presence {
  if (!lastSeen) return "never";
  const timestamp = Date.parse(lastSeen);
  if (!Number.isFinite(timestamp) || timestamp > now) return "offline";
  const elapsed = now - timestamp;
  if (elapsed <= 15 * 60_000) return "recent";
  if (elapsed <= 30 * 60_000) return "late";
  return "offline";
}

export function formatSeen(lastSeen: string | null, now: number) {
  if (!lastSeen) return "Jamais vu";
  const elapsed = now - Date.parse(lastSeen);
  if (!Number.isFinite(elapsed) || elapsed < 0) return "Date inconnue";
  if (elapsed < 60_000) return "Il y a moins d’une minute";
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 60) return `Il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Il y a ${hours} h`;
  return `Il y a ${Math.floor(hours / 24)} j`;
}

export function displayDevice(device: Device, now: number): DisplayDevice {
  const presence = getPresence(device.last_seen_at, now);
  const labels = { recent: "Présence récente", late: "Signal en retard", offline: "État actuel inconnu", never: "Jamais vu" };
  const uptime = device.uptime_seconds;
  return {
    id: device.id, name: device.name, location: device.location || "Emplacement non précisé",
    presence, presenceLabel: labels[presence],
    tone: presence === "recent" ? "green" : presence === "late" ? "amber" : "neutral",
    lastSeen: formatSeen(device.last_seen_at, now), seenDate: device.last_seen_at,
    state: device.last_seen_at ? states[device.request_state] : states.inconnu,
    stateKind: device.last_seen_at ? device.request_state : "inconnu",
    wifi: device.wifi_rssi === null ? "Non reçu" : `${device.wifi_rssi} dBm`,
    uptime: uptime === null ? "Non reçue" : `${Math.floor(uptime / 86400)} j ${Math.floor(uptime % 86400 / 3600)} h`,
    version: device.firmware_version || "Non reçue", micropython: device.micropython_version || "Non reçue",
    reboots: device.reboot_count === null ? "Non reçu" : String(device.reboot_count),
    note: presence === "never" ? "Ce boîtier est enregistré. Aucun signal de présence n’a encore été reçu." :
      presence === "recent" ? "Les informations affichées correspondent au dernier signal reçu." :
      "Le dernier signal est ancien. L’état actuel du boîtier est inconnu.",
    lastError: device.last_error === "pushbullet_quota_mensuel"
      ? "Quota mensuel Pushbullet atteint. Vérifiez le compte Pushbullet pour rétablir les envois."
      : device.last_error,
  };
}

export function needsAttention(device: Pick<DisplayDevice, "presence" | "lastError">): boolean {
  return device.presence !== "recent" || Boolean(device.lastError);
}
