export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const res = await fetch("/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Eye-Client": "workspace",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res
    .json()
    .catch(() => ({ detail: "The server could not complete this request." }));
  if (res.status === 401) window.dispatchEvent(new Event("eye-auth-expired"));
  if (!res.ok)
    throw new ApiError(
      res.status,
      typeof data.detail === "string"
        ? data.detail
        : "Check your inputs and try again.",
    );
  return data as T;
}
export type Instrument = {
  segment?: string;
  timeframe?: string;
  symbol: string;
  name: string;
  start: string;
  end: string;
  source: string;
  currency: string;
};
export type Quote = Instrument & {
  price: number;
  change_pct?: number;
  observed_at: string;
  status: string;
  tradable: boolean;
  sparkline?: number[];
};
export type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};
export type Position = {
  symbol: string;
  qty: number;
  avg_price: number;
  price: number;
  value: number;
  pnl: number;
  observed_at: string;
  status: string;
};
export type Portfolio = {
  currency?: string;
  cash: number;
  initial: number;
  realized: number;
  reserved_cash: number;
  positions: Position[];
  total: number;
  unrealized: number;
  scope: string;
  valuation_note: string;
};
export type Order = {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  order_type: string;
  price: string;
  status: string;
  fill_price: number | null;
  filled_at: string | null;
  created_at: string;
  scope: string;
  reason?: string;
};
export type Replay = {
  currency?: string;
  id: string;
  symbol: string;
  date: string;
  current_price: number;
  candles: Candle[];
  portfolio: Portfolio;
  benchmark_value: number;
  benchmark_return_pct: number;
  ended: boolean;
  source: string;
  execution_rule: string;
  equity: { date: string; value: number; benchmark: number }[];
};
export type Analysis = {
  symbol: string;
  as_of: string;
  source: string;
  indicators: { name: string; value: number; explanation: string }[];
  fundamentals_status: string;
};
export type Metrics = {
  mae: number;
  rmse: number;
  directional_accuracy_pct: number;
  strategy_return_pct: number;
  max_drawdown_pct: number;
  test_trades: number;
};
export type Forecast = {
  status?: string;
  currency?: string;
  folds?: {
    fold: number;
    train_end: string;
    test_start: string;
    test_end: string;
    selected_model: string;
  }[];
  symbol: string;
  horizon_sessions: number;
  version: string;
  selected_model: string;
  as_of: string;
  current_price: number;
  predicted_target: number;
  expected_return_pct: number;
  beats_baseline: boolean;
  interval: {
    lower: number;
    upper: number;
    test_coverage_pct: number;
    method: string;
    caveat: string;
  };
  test: Record<string, Metrics>;
  validation: Record<string, Metrics>;
  split: Record<string, string | number>;
  training: Record<string, string | number>;
  strategy_assumptions: string;
  test_points: {
    date: string;
    actual: number;
    prediction: number;
    baseline: number;
  }[];
  notes: string[];
};
export type Lesson = {
  segment?: string;
  practice?: string;
  id: string;
  title: string;
  level: string;
  minutes: number;
  body: string;
  question: string;
  options: string[];
  progress: { passed: boolean } | null;
};
