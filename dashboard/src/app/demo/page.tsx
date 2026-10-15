import { DashboardView } from "@/components/dashboard-view";
import { displayDevice } from "@/lib/device-status";
import type { Device } from "@/lib/supabase/database.types";

export default function Demo() {
  const now = Date.UTC(2026, 9, 16, 12);
  const common: Device = {
    id: "DEMO-01", household_id: "demo", name: "Lit", location: "Chambre",
    created_at: new Date(now).toISOString(), last_seen_at: new Date(now - 2 * 60_000).toISOString(),
    request_state: "repos", firmware_version: "Démo 0.2", micropython_version: "Démo",
    wifi_rssi: -58, uptime_seconds: 187200, reboot_count: 1, last_error: null,
  };
  const devices = [common, {
    ...common, id: "DEMO-02", name: "Salle de bains", location: "Salle de bains",
    last_seen_at: new Date(now - 22 * 60_000).toISOString(), wifi_rssi: -72, uptime_seconds: 115200,
  }];
  return <DashboardView householdName="Logement de démonstration" devices={devices.map(device => displayDevice(device, now))} demo />;
}
