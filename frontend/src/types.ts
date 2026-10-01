export type AppMode = "offline" | "online";

export interface TableSeat {
  seat_no: number;
  player_id: string;
  stack: number;
  status: string;
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
