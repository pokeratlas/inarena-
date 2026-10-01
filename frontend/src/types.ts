export type AppMode = "offline" | "online";

export interface TableSeat {
  seat_no: number;
  player_id: string;
  stack: number;
  status: string;
  rebuy_count: number;
  addon_used: number;
  eliminated_at: string | null;
  finish_place: number | null;
  updated_at: string;
}

export interface ActiveHand {
  hand_id: string;
  street: string;
  pot: number;
  button_seat: number | null;
  action_seat: number | null;
  state: Record<string, unknown>;
  started_at: string;
  updated_at: string;
}

export interface TableState {
  id: string;
  name: string;
  status: string;
  small_blind: number;
  big_blind: number;
  last_button_seat: number | null;
  table_mode: "cash" | "tournament";
  starting_stack: number;
  blind_schedule: Array<{
    small_blind: number;
    big_blind: number;
    duration_seconds: number;
  }>;
  blind_level_index: number;
  blind_level_started_at: number | null;
  blind_schedule_status: "running" | "paused";
  blind_schedule_paused_at: number | null;
  cash_buyin_min: number;
  cash_buyin_max: number;
  rebuy_enabled: boolean;
  rebuy_stack: number;
  rebuy_max_per_player: number;
  addon_enabled: boolean;
  addon_stack: number;
  rebuy_window_open: boolean;
  addon_window_open: boolean;
  winner_player_id: string | null;
  finished_at: string | null;
  tournament_status:
    | "scheduled"
    | "registering"
    | "running"
    | "finished"
    | "cancelled";
  scheduled_start_at: number | null;
  registration_open_at: number | null;
  registration_close_at: number | null;
  late_registration_close_at: number | null;
  registration_count: number;
  seats: TableSeat[];
  active_hand: ActiveHand | null;
  created_at: string;
  updated_at: string;
}

export interface TableEvent {
  seq: number;
  table_id: string;
  event_type: string;
  payload: TableState;
  created_at: string;
}


export interface PlayerTableView {
  table: TableState;
  player_id: string;
  hole_cards: string[];
}


export interface HandHistoryEntry {
  hand_id: string;
  pot: number;
  payouts: Record<string, number>;
  final_stacks: Record<string, number>;
  completed_at: string;
}

export interface HandActionEntry {
  action_no: number;
  player_id: string;
  seat_no: number;
  action: string;
  amount: number | null;
  state: Record<string, unknown>;
  created_at: string;
}


export interface PlayerHandHistoryEntry {
  hand_id: string;
  table_id: string;
  pot: number;
  hole_cards: string[];
  board: string[];
  payout: number;
  final_stack: number;
  completed_at: string;
}


export interface OperatorDashboard {
  tables_total: number;
  tables_playing: number;
  tables_paused: number;
  cash_tables: number;
  tournament_tables: number;
  active_hands: number;
  seated_players: number;
  eliminated_players: number;
  active_sessions: number;
  operator_audit_entries: number;
  ledger_totals: Record<string, number>;
  tables: Array<{
    id: string;
    name: string;
    status: string;
    table_mode: "cash" | "tournament";
    small_blind: number;
    big_blind: number;
    blind_level_index: number;
    blind_schedule_status: string;
    rebuy_window_open: number;
    addon_window_open: number;
    winner_player_id: string | null;
    finished_at: string | null;
    tournament_status: string;
    scheduled_start_at: number | null;
    late_registration_close_at: number | null;
  }>;
}

export interface OperatorAuditEntry {
  id: number;
  table_id: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface PlayerBalance {
  user_id: string;
  balance: number;
}


export interface TournamentRegistration {
  table_id: string;
  user_id: string;
  status: "registered" | "withdrawn" | "not_registered";
  registered_at: string | null;
  withdrawn_at: string | null;
}
