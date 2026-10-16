export type Household = {
  id: string;
  owner_id: string;
  name: string;
  created_at: string;
};

export type Device = {
  id: string;
  household_id: string;
  name: string;
  location: string;
  created_at: string;
  last_seen_at: string | null;
  request_state: "inconnu" | "repos" | "en_attente" | "confirmee" | "annulee";
  request_id: string | null;
  firmware_version: string | null;
  micropython_version: string | null;
  wifi_rssi: number | null;
  uptime_seconds: number | null;
  reboot_count: number | null;
  last_error: string | null;
};

export type DeviceEvent = {
  id: number;
  device_id: string;
  event_type: string;
  received_at: string;
  request_id: string | null;
};

export type DashboardMember = {
  user_id: string;
  email: string | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  updated_at: string;
};

export type Database = {
  public: {
    Tables: {
      dashboard_members: {
        Row: DashboardMember;
        Insert: never;
        Update: never;
        Relationships: [];
      };
      households: {
        Row: Household;
        Insert: { id?: string; owner_id: string; name: string; created_at?: string };
        Update: { name?: string };
        Relationships: [];
      };
      devices: {
        Row: Device;
        Insert: { household_id: string; name: string; location?: string };
        Update: { name?: string; location?: string };
        Relationships: [{ foreignKeyName: "devices_household_id_fkey"; columns: ["household_id"]; isOneToOne: false; referencedRelation: "households"; referencedColumns: ["id"] }];
      };
      device_events: {
        Row: DeviceEvent;
        Insert: never;
        Update: never;
        Relationships: [{ foreignKeyName: "device_events_device_id_fkey"; columns: ["device_id"]; isOneToOne: false; referencedRelation: "devices"; referencedColumns: ["id"] }];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
      is_dashboard_admin: { Args: Record<string, never>; Returns: boolean };
      has_dashboard_access: { Args: Record<string, never>; Returns: boolean };
      create_shared_household: { Args: { p_name: string }; Returns: undefined };
      set_dashboard_access: { Args: { p_user_id: string; p_status: "approved" | "rejected" }; Returns: undefined };
      set_device_key: { Args: { p_device_id: string; p_token_hash: string }; Returns: undefined };
      ingest_device_report: { Args: { p_device_id: string; p_token: string; p_report: import("../device-report").DeviceReport }; Returns: { status: "accepted" | "obsolete" | "unauthorized" | "invalid" | "rate_limited" } };
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
};
