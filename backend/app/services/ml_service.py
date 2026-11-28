"""LSTM price-forecast service.

Implements the pipeline described in ``Untitled.md``:

1. Build 60-bar windows of daily log-returns from real OHLCV candles.
2. Predict the *next log-return* with three quantile outputs (10th, 50th, 90th)
   trained on pinball (quantile) loss.
3. Validate with a walk-forward holdout and compare against a naive
   last-value baseline before showing any forecast.

If PyTorch is not installed (or a symbol lacks enough history) the service
falls back to an empirically-calibrated quantile forecaster built directly from
the instrument's own historical return distribution, so the endpoint always
returns correct, data-driven, deterministic output.

On memory-constrained hosts (for example Render's free 512 MB instance) PyTorch
is deliberately skipped so a single estimate request cannot OOM the process.
Set STOCKVISTA_DISABLE_TORCH=true to force that mode; Render sets RENDER=true,
which enables it automatically. Local development still uses the real LSTM.
"""

import math
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.services.market_ingest import market_ingest, normalize_symbol, CRYPTO_MAP
from app.schemas.schemas import PredictionResponse, PredictionPoint

# ----- Optional PyTorch (real neural network) -----
def _torch_disabled() -> bool:
    """Explicit STOCKVISTA_DISABLE_TORCH wins; otherwise off on Render (512 MB)."""
    flag = os.getenv("STOCKVISTA_DISABLE_TORCH", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return os.getenv("RENDER", "").strip().lower() in {"1", "true", "yes"}


try:
    if _torch_disabled():
        raise ImportError("PyTorch disabled on this host to stay within memory limits")
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except Exception:  # pragma: no cover - environment without torch
    torch = None
    nn = None
    TORCH_AVAILABLE = False


QUANTILES = (0.1, 0.5, 0.9)


def _trades_24x7(sym: str) -> bool:
    """Crypto pairs trade every day, so their forecast steps are calendar days."""
    return sym in CRYPTO_MAP or sym.endswith("USDT")


def _business_days(last_date: Optional[str], horizon: int, every_day: bool = False) -> List[str]:
    """Return ISO date labels starting after the last historical bar.

    Stocks step over weekends (one step = one trading day). Crypto bars are
    24/7, so with every_day=True each step is one calendar day.
    """
    try:
        current = datetime.strptime(last_date[:10], "%Y-%m-%d") if last_date else datetime.utcnow()
    except (ValueError, TypeError):
        current = datetime.utcnow()
    dates = []
    while len(dates) < horizon:
        current += timedelta(days=1)
        if every_day or current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
    return dates


if TORCH_AVAILABLE:

    class QuantileRecurrent(nn.Module):
        """Two-layer recurrent net (LSTM or GRU) with a 3-output quantile head.

        ``kind`` selects the cell type and ``bidirectional`` toggles a Bi-LSTM /
        Bi-GRU first layer, so the dashboard's LSTM / Bi-LSTM / GRU choices map
        to genuinely different networks.
        """

        def __init__(self, kind: str = "lstm", hidden: int = 48, bidirectional: bool = False):
            super().__init__()
            cell = nn.GRU if kind == "gru" else nn.LSTM
            self.rnn1 = cell(input_size=1, hidden_size=hidden, batch_first=True, bidirectional=bidirectional)
            width = hidden * (2 if bidirectional else 1)
            self.dropout = nn.Dropout(0.2)
            self.rnn2 = cell(width, hidden // 2, batch_first=True)
            self.fc = nn.Linear(hidden // 2, len(QUANTILES))

        def forward(self, x):  # x: (batch, window, 1)
            out, _ = self.rnn1(x)
            out = self.dropout(out)
            out, _ = self.rnn2(out)
            return self.fc(out[:, -1, :])  # (batch, 3)


def _pinball_loss(pred, target, quantiles=QUANTILES):
    """Pinball / quantile loss averaged over the three quantile outputs."""
    losses = []
    for i, q in enumerate(quantiles):
        err = target - pred[:, i]
        losses.append(torch.maximum(q * err, (q - 1) * err))
    return torch.stack(losses, dim=1).mean()


def _json_safe(value: Any) -> Any:
    """Replace NaN/inf (which JSON cannot encode) with None, recursively."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


class LSTMPredictionEngine:
    WINDOW = 60           # lookback bars fed to the network (per Untitled.md spec)
    MIN_SAMPLES = 90      # minimum history required to train an LSTM
    MODEL_TTL = 900.0     # seconds before a trained model is refreshed
    RESULT_TTL = 60.0     # seconds a prediction result is cached
    MAX_MODELS = 6        # trained networks kept in memory at once
    MAX_RESULTS = 128     # cached prediction responses

    def __init__(self):
        self._architectures = {
            "lstm": self._arch_spec("LSTM", bidirectional=False, cell="LSTM"),
            "bilstm": self._arch_spec("Bi-LSTM", bidirectional=True, cell="LSTM"),
            "gru": self._arch_spec("GRU", bidirectional=False, cell="GRU"),
        }
        self.architecture = self._architectures["lstm"]
        self._model_cache: Dict[str, Tuple[Any, Dict[str, Any], float]] = {}
        self._result_cache: Dict[str, Tuple[PredictionResponse, float]] = {}
        self._lock = threading.Lock()
        # One training job at a time: parallel requests for different symbols
        # would otherwise each hold a model, optimiser and tensors in memory.
        self._train_lock = threading.Lock()

    def _arch_spec(self, label: str, bidirectional: bool, cell: str) -> Dict[str, Any]:
        first = cell + (" (bidirectional)" if bidirectional else "")
        return {
            "model_type": f"Multi-layer {label} Neural Network",
            "framework": "PyTorch" if TORCH_AVAILABLE else "NumPy quantile forecaster",
            "layers": [
                {"type": first, "units": 48, "return_sequences": True},
                {"type": "Dropout", "rate": 0.2},
                {"type": cell, "units": 24, "return_sequences": False},
                {"type": "Dense", "units": 3, "activation": "linear"},
            ],
            "bidirectional": bidirectional,
            "loss_function": "Pinball Quantile Loss (q=0.1, 0.5, 0.9)",
            "sequence_window": f"{self.WINDOW} bars historical lookback",
            "features": "Close price (log returns)",
            "target": "next-period log return (quantile regression)",
        }

    def _build_model(self, model: str):
        if not TORCH_AVAILABLE:
            return None
        if model == "gru":
            return QuantileRecurrent(kind="gru", hidden=48, bidirectional=False)
        if model == "bilstm":
            return QuantileRecurrent(kind="lstm", hidden=48, bidirectional=True)
        return QuantileRecurrent(kind="lstm", hidden=48, bidirectional=False)

    # ========================================================
    # DATA
    # ========================================================
    def _load_series(self, symbol: str) -> Tuple[List[str], np.ndarray, str]:
        """Load verified real candles only.

        Synthetic fallback candles are explicitly excluded so the LSTM can never
        train on fabricated prices and then claim to be a real market forecast.
        """
        candles = [
            c for c in market_ingest.get_candles(symbol, "1d", 500)
            if not getattr(c, "is_synthetic", False)
            and getattr(c, "source", "unknown") != "synthetic"
        ]
        if not candles:
            return [], np.array([]), "unavailable"
        source = candles[-1].source or "unknown"
        times = [c.time for c in candles]
        closes = np.array([c.close for c in candles], dtype=np.float64)
        valid = np.isfinite(closes) & (closes > 0)
        closes = closes[valid]
        times = [t for t, ok in zip(times, valid) if ok]
        return times, closes, source

    # ========================================================
    # PUBLIC API
    # ========================================================
    def predict_symbol(self, symbol: str, horizon_days: int = 7, model: str = "lstm") -> PredictionResponse:
        sym = normalize_symbol(symbol)
        if not sym:
            raise ValueError("Invalid symbol")
        model = (model or "lstm").lower().strip()
        if model not in self._architectures:
            model = "lstm"
        horizon_days = max(1, min(int(horizon_days), 90))

        cache_key = f"{sym}:{horizon_days}:{model}"
        with self._lock:
            cached = self._result_cache.get(cache_key)
            if cached and (time.time() - cached[1]) < self.RESULT_TTL:
                return cached[0]

        try:
            result = self._compute_prediction(sym, horizon_days, model)
        except (OverflowError, FloatingPointError, ZeroDivisionError) as exc:
            raise ValueError(f"Estimate for {sym} is numerically unstable: {exc}")
        with self._lock:
            now = time.time()
            self._result_cache[cache_key] = (result, now)
            if len(self._result_cache) > self.MAX_RESULTS:
                for k in [k for k, v in self._result_cache.items() if now - v[1] >= self.RESULT_TTL]:
                    self._result_cache.pop(k, None)
                while len(self._result_cache) > self.MAX_RESULTS:
                    oldest = min(self._result_cache, key=lambda k: self._result_cache[k][1])
                    self._result_cache.pop(oldest, None)
        return result

    def get_backtest_scorecard(self, symbol: str, model: str = "lstm") -> Dict[str, Any]:
        sym = normalize_symbol(symbol)
        if not sym:
            raise ValueError("Invalid symbol")
        model = (model or "lstm").lower().strip()
        if model not in self._architectures:
            model = "lstm"
        pred = self.predict_symbol(sym, 7, model)
        m = pred.accuracy_metrics
        backtest = m.get("backtest", {})
        beats = bool(m.get("beats_naive_baseline", False))
        return {
            "symbol": sym,
            "model_architecture": self._architectures[model],
            "validation_method": m.get("validation_method", "Walk-forward holdout, no shuffling across time"),
            "historical_runs": m.get("validation_samples", 0),
            "profitable_directional_calls_pct": m.get("directional_accuracy_pct", 0.0),
            "win_loss_ratio": backtest.get("win_loss_ratio", 0.0),
            "max_drawdown_observed": backtest.get("max_drawdown_pct", 0.0),
            "sharpe_ratio_of_strategy": backtest.get("sharpe_ratio", 0.0),
            "status": "CHAMPION_ACTIVE" if beats else "CHALLENGER_BASELINE_WINS",
            "beats_naive_baseline": beats,
        }

    # ========================================================
    # CORE
    # ========================================================
    def _compute_prediction(self, sym: str, horizon: int, model: str = "lstm") -> PredictionResponse:
        times, closes, candle_source = self._load_series(sym)
        if len(closes) < 2:
            raise ValueError(
                f"No verified historical price data for {sym}. "
                "Connect a live broker/feed or choose a tracked instrument."
            )

        quote = market_ingest.get_quote(sym)
        quote_source = quote.source if quote else "unavailable"
        # Anchor to the freshest verified quote; never to a fabricated price.
        if quote and not quote.is_synthetic and quote.price > 0:
            current_price = float(quote.price)
        else:
            current_price = float(closes[-1])

        data_source = quote_source if quote_source != "unavailable" else candle_source
        model_used = "empirical-quantile"
        points: List[PredictionPoint] = []
        metrics: Dict[str, Any] = {}

        lstm_out = None
        if TORCH_AVAILABLE and len(closes) >= self.MIN_SAMPLES:
            lstm_out = self._lstm_forecast(sym, model, closes, horizon, current_price, times)
            if lstm_out is not None:
                points, metrics = lstm_out
                model_used = "lstm"

        if not points:
            points, metrics = self._empirical_forecast(sym, closes, horizon, current_price, times)

        metrics["data_source"] = data_source
        metrics["data_as_of"] = (quote.as_of if quote and quote.as_of else None)
        metrics["features"] = "Close price (log returns)"

        target_price = points[-1].predicted
        expected_return = round(((target_price - current_price) / current_price) * 100, 2) if current_price else 0.0
        confidence = self._confidence(metrics)

        if model_used == "lstm":
            metrics["framework"] = f"PyTorch {self._architectures[model]['model_type'].replace('Multi-layer ', '').replace(' Neural Network', '')}"
            metrics["model"] = model
        else:
            metrics["framework"] = "NumPy empirical quantiles"
            metrics["model"] = "empirical"
        metrics["probability_confidence"] = confidence
        metrics["history_bars"] = int(len(closes))
        metrics["history_years"] = round(max(0, len(closes) - 1) / 252.0, 1)
        metrics = _json_safe(metrics)
        if not all(math.isfinite(v) for v in (target_price, expected_return, current_price)):
            raise ValueError(f"Estimate for {sym} produced non-finite values; try again later.")

        return PredictionResponse(
            symbol=sym,
            horizon=f"{horizon}D",
            current_price=round(current_price, 2),
            predicted_target=round(target_price, 2),
            expected_return_pct=expected_return,
            lower_bound=points[-1].lower_band,
            upper_bound=points[-1].upper_band,
            confidence_score=confidence,
            accuracy_metrics=metrics,
            forecast_points=points,
            predictions=points,
            data_source=data_source,
            as_of=(quote.as_of if quote and quote.as_of else None),
            disclaimer=(
                "SEBI Compliance: Model outputs are statistical deep-learning forecasts "
                "based on historical data. They do not constitute financial advice or "
                "trade recommendations."
            ),
        )

    # ========================================================
    # LSTM PATH
    # ========================================================
    def _get_or_train(self, sym: str, model_type: str, closes: np.ndarray) -> Optional[Tuple[Any, Dict[str, Any]]]:
        cache_key = f"{sym}:{model_type}:{len(closes)}"

        def _cached():
            with self._lock:
                hit = self._model_cache.get(cache_key)
                if hit and (time.time() - hit[2]) < self.MODEL_TTL:
                    return hit[0], hit[1]
            return None

        hit = _cached()
        if hit:
            return hit
        # Training takes seconds and hundreds of MB. If another request is
        # already training, do not queue behind it (queued requests pin the
        # shared threadpool and stall login and every other sync route):
        # return None so the caller serves the cheap empirical estimate.
        if not self._train_lock.acquire(timeout=1.0):
            return None
        try:
            hit = _cached()  # another request may have trained it meanwhile
            if hit:
                return hit
            try:
                trained = self._train_model(closes, model_type)
            except Exception as e:  # pragma: no cover
                print(f"[LSTM Training Error] {sym}: {e}")
                return None
        finally:
            self._train_lock.release()
        if trained is None:
            return None
        model, scale, holdout, epochs = trained
        meta = {"scale": scale, "holdout": holdout, "epochs": epochs}
        with self._lock:
            now = time.time()
            # The key includes the bar count, so yesterday's model for the same
            # symbol would otherwise live forever next to today's.
            prefix = f"{sym}:{model_type}:"
            for k in [k for k, v in self._model_cache.items()
                      if k.startswith(prefix) or now - v[2] >= self.MODEL_TTL]:
                self._model_cache.pop(k, None)
            self._model_cache[cache_key] = (model, meta, now)
            while len(self._model_cache) > self.MAX_MODELS:
                oldest = min(self._model_cache, key=lambda k: self._model_cache[k][2])
                self._model_cache.pop(oldest, None)
        return model, meta

    def _train_model(self, closes: np.ndarray, model_type: str = "lstm"):
        returns = np.diff(np.log(closes))
        if len(returns) < self.MIN_SAMPLES:
            return None

        window = self.WINDOW
        total_windows = len(returns) - window
        # Hold out the tail for walk-forward validation (never shuffled).
        holdout = max(20, int(0.2 * total_windows))
        train_n = total_windows - holdout
        if train_n < 40:
            return None

        # Scale is fitted on the TRAINING window only — no holdout leakage.
        scale = float(np.std(returns[:train_n + window])) or 1e-4
        norm = returns / scale

        # Build supervised windows
        X, y = [], []
        for i in range(total_windows):
            X.append(norm[i:i + window])
            y.append(norm[i + window])
        X = np.array(X, dtype=np.float32)[..., None]
        y = np.array(y, dtype=np.float32)[:, None]

        Xtr = torch.tensor(X[:train_n])
        ytr = torch.tensor(y[:train_n])

        torch.manual_seed(42)
        model = self._build_model(model_type)
        opt = torch.optim.Adam(model.parameters(), lr=0.01)
        model.train()

        best = float("inf")
        patience = 0
        epochs_run = 0
        for _epoch in range(80):
            epochs_run += 1
            perm = torch.randperm(len(Xtr))
            epoch_loss = 0.0
            for i in range(0, len(Xtr), 64):
                idx = perm[i:i + 64]
                opt.zero_grad()
                pred = model(Xtr[idx])
                loss = _pinball_loss(pred, ytr[idx])
                loss.backward()
                opt.step()
                epoch_loss += loss.item() * len(idx)
            epoch_loss /= len(Xtr)
            if epoch_loss < best - 1e-4:
                best = epoch_loss
                patience = 0
            else:
                patience += 1
                if patience >= 10:
                    break

        model.eval()
        return model, scale, holdout, epochs_run

    @torch.no_grad() if TORCH_AVAILABLE else (lambda f: f)
    def _predict_quantiles(self, model, windows: np.ndarray) -> np.ndarray:
        """Run the network on a batch of windows -> (batch, 3) quantile returns."""
        x = torch.tensor(np.asarray(windows, dtype=np.float32))
        if x.ndim == 1:
            x = x[None, :, None]
        elif x.ndim == 2:
            x = x[:, :, None]
        return model(x).numpy()

    def _lstm_forecast(self, sym: str, model_type: str, closes: np.ndarray, horizon: int,
                       current_price: float, times: Optional[List[str]] = None):
        trained = self._get_or_train(sym, model_type, closes)
        if trained is None:
            return None
        model, meta = trained
        scale = meta["scale"]
        holdout = meta["holdout"]

        returns = np.diff(np.log(closes))
        norm = returns / scale

        # --- Walk-forward validation on the held-out tail (no leakage) ---
        dir_correct = 0
        abs_errs, sq_errs, base_errs, ma_errs = [], [], [], []
        actuals, preds = [], []
        correct_moves, wrong_moves = [], []
        strat_returns = []

        n = len(returns)
        start = n - holdout
        windows, idxs = [], []
        for i in range(start, n):
            if i - self.WINDOW < 0:
                continue
            windows.append(norm[i - self.WINDOW:i])
            idxs.append(i)

        if windows:
            q_all = self._predict_quantiles(model, np.array(windows))
            for row, i in zip(q_all, idxs):
                r50 = float(row[1]) * scale
                pred_price = closes[i] * math.exp(r50)
                actual_price = closes[i + 1]
                actual_ret = returns[i]
                preds.append(pred_price)
                actuals.append(actual_price)
                abs_errs.append(abs(pred_price - actual_price))
                sq_errs.append((pred_price - actual_price) ** 2)
                base_errs.append(abs(closes[i] - actual_price))
                ma_baseline = float(np.mean(closes[max(0, i - 5):i + 1]))
                ma_errs.append(abs(ma_baseline - actual_price))
                if (r50 >= 0) == (actual_ret >= 0):
                    dir_correct += 1
                    correct_moves.append(abs(actual_ret))
                else:
                    wrong_moves.append(abs(actual_ret))
                strat_returns.append(actual_ret if r50 >= 0 else -actual_ret)

        metrics = self._build_metrics(
            preds, actuals, abs_errs, sq_errs, base_errs,
            dir_correct, correct_moves, wrong_moves, strat_returns,
            ma_errs,
        )
        metrics["forecast_method"] = "lstm-quantile"
        metrics["epochs_trained"] = meta.get("epochs")

        # --- Forward forecast: autoregressive rollout of the median quantile ---
        recent = list(norm[-self.WINDOW:])
        last_price = current_price
        cum_log = 0.0
        cum_var = 0.0
        points: List[PredictionPoint] = []
        forecast_dates = _business_days(times[-1] if times else None, horizon, every_day=_trades_24x7(sym))

        for step in range(1, horizon + 1):
            q = self._predict_quantiles(model, np.array(recent[-self.WINDOW:]))[0] * scale
            r50, r10, r90 = float(q[1]), float(q[0]), float(q[2])
            # Quantile heads can cross; clamp to a valid monotone band.
            r10 = min(r10, r50)
            r90 = max(r90, r50)
            half = max(abs(r90 - r10) / 2.0, 1e-5)
            cum_log += r50
            cum_var += half * half
            recent.append(r50 / scale)
            median_price = last_price * math.exp(cum_log)
            spread = math.sqrt(cum_var)
            lower = last_price * math.exp(cum_log - spread)
            upper = last_price * math.exp(cum_log + spread)
            iso_date = forecast_dates[step - 1]
            points.append(PredictionPoint(
                day=datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d %b"),
                date=iso_date,
                predicted=round(max(median_price, 0.01), 2),
                lower_band=round(max(lower, 0.01), 2),
                upper_band=round(max(upper, 0.01), 2),
            ))

        return points, metrics

    # ========================================================
    # EMPIRICAL QUANTILE PATH (fallback / no torch)
    # ========================================================
    def _empirical_forecast(self, sym: str, closes: np.ndarray, horizon: int,
                            current_price: float, times: Optional[List[str]] = None):
        returns = np.diff(np.log(closes)) if len(closes) >= 2 else np.array([0.0])

        # One-step walk-forward error metrics (predict using expanding median drift)
        dir_correct = 0
        abs_errs, sq_errs, base_errs, ma_errs = [], [], [], []
        actuals, preds = [], []
        correct_moves, wrong_moves, strat_returns = [], [], []
        if len(returns) >= 10:
            start = max(1, int(len(returns) * 0.7))
            for i in range(start, len(returns)):
                hist = returns[:i]
                drift = float(np.median(hist))
                r_pred = drift
                pred_price = closes[i] * math.exp(r_pred)
                actual_price = closes[i + 1]
                actual_ret = returns[i]
                preds.append(pred_price)
                actuals.append(actual_price)
                abs_errs.append(abs(pred_price - actual_price))
                sq_errs.append((pred_price - actual_price) ** 2)
                base_errs.append(abs(closes[i] - actual_price))
                ma_baseline = float(np.mean(closes[max(0, i - 5):i + 1]))
                ma_errs.append(abs(ma_baseline - actual_price))
                if (r_pred >= 0) == (actual_ret >= 0):
                    dir_correct += 1
                    correct_moves.append(abs(actual_ret))
                else:
                    wrong_moves.append(abs(actual_ret))
                strat_returns.append(actual_ret if r_pred >= 0 else -actual_ret)

        metrics = self._build_metrics(
            preds, actuals, abs_errs, sq_errs, base_errs,
            dir_correct, correct_moves, wrong_moves, strat_returns,
            ma_errs,
        )

        # Quantile path from empirical h-step return distribution
        last_price = current_price
        forecast_dates = _business_days(times[-1] if times else None, horizon, every_day=_trades_24x7(sym))
        points: List[PredictionPoint] = []
        for step in range(1, horizon + 1):
            if len(returns) > step + 5:
                h_returns = np.array([returns[i:i + step].sum() for i in range(0, len(returns) - step + 1)])
                q10, q50, q90 = np.percentile(h_returns, [10, 50, 90])
            else:
                drift = float(np.median(returns))
                vol = float(np.std(returns)) or 1e-4
                q50 = drift * step
                q10 = q50 - 1.2816 * vol * math.sqrt(step)
                q90 = q50 + 1.2816 * vol * math.sqrt(step)
            iso_date = forecast_dates[step - 1]
            points.append(PredictionPoint(
                day=datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d %b"),
                date=iso_date,
                predicted=round(max(last_price * math.exp(float(q50)), 0.01), 2),
                lower_band=round(max(last_price * math.exp(float(q10)), 0.01), 2),
                upper_band=round(max(last_price * math.exp(float(q90)), 0.01), 2),
            ))

        metrics["forecast_method"] = "empirical-quantile"
        return points, metrics

    # ========================================================
    # METRICS HELPERS
    # ========================================================
    def _build_metrics(self, preds, actuals, abs_errs, sq_errs, base_errs,
                       dir_correct, correct_moves, wrong_moves, strat_returns,
                       ma_errs=None) -> Dict[str, Any]:
        n = len(abs_errs)
        if n == 0:
            return {
                "mean_absolute_error_mae": None,
                "root_mean_squared_error_rmse": None,
                "r2_score": None,
                "directional_accuracy_pct": None,
                "beats_naive_baseline": False,
                "baseline_last_value_mae": None,
                "improvement_over_baseline_pct": None,
                "validation_samples": 0,
                "last_retrained": datetime.utcnow().strftime("%Y-%m-%d"),
                "validation_method": "Insufficient history for walk-forward validation",
                "note": "Forecast is an empirical quantile path; backtest needs more candles.",
            }

        mae = float(np.mean(abs_errs))
        rmse = float(np.sqrt(np.mean(sq_errs)))
        base_mae = float(np.mean(base_errs))
        ma_mae = float(np.mean(ma_errs)) if ma_errs else base_mae
        mean_actual = float(np.mean(actuals))
        ss_tot = float(np.sum((np.array(actuals) - mean_actual) ** 2))
        ss_res = float(np.sum(sq_errs))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        dir_acc = round(100.0 * dir_correct / n, 1)
        improvement = round((base_mae - mae) / base_mae * 100, 2) if base_mae > 0 else 0.0

        avg_correct = float(np.mean(correct_moves)) if correct_moves else 0.0
        avg_wrong = float(np.mean(wrong_moves)) if wrong_moves else 0.0
        # No wrong calls means the ratio is undefined (it used to report the win count).
        win_loss = round(avg_correct / avg_wrong, 2) if avg_wrong > 0 else None

        strat = np.array(strat_returns, dtype=np.float64)
        if len(strat) > 1 and np.std(strat) > 0:
            sharpe = round(float(np.mean(strat) / np.std(strat) * math.sqrt(252)), 2)
        else:
            sharpe = 0.0
        equity = np.cumprod(1.0 + strat) if len(strat) else np.array([1.0])
        peak = np.maximum.accumulate(equity)
        max_dd = round(float(np.min(equity / peak - 1.0) * 100), 2) if len(equity) else 0.0

        return {
            "mean_absolute_error_mae": round(mae, 2),
            "root_mean_squared_error_rmse": round(rmse, 2),
            "r2_score": round(r2, 4),
            "directional_accuracy_pct": dir_acc,
            "beats_naive_baseline": mae < base_mae,
            "baseline_last_value_mae": round(base_mae, 2),
            "baseline_moving_average_mae": round(ma_mae, 2),
            "beats_moving_average_baseline": mae < ma_mae,
            "improvement_over_baseline_pct": improvement,
            "validation_samples": int(len(abs_errs)),
            "last_retrained": datetime.utcnow().strftime("%Y-%m-%d"),
            "validation_method": "Walk-forward holdout on the most recent bars, train-window scaling, no shuffling across time",
            "backtest": {
                "win_loss_ratio": win_loss,
                "sharpe_ratio": sharpe,
                "max_drawdown_pct": max_dd,
            },
        }

    def _confidence(self, metrics: Dict[str, Any]) -> float:
        """How much the backtest supports the forecast, on a 0-100 scale.

        50 means "no better than a coin flip". The score is built only from
        the measured EDGE: directional accuracy above 50%, and error versus
        the naive last-value baseline. Price-level R^2 is deliberately left
        out: it is ~0.95 for any forecast that stays near the last price, so
        it inflated every score by several points.
        """
        dir_acc = metrics.get("directional_accuracy_pct")
        improvement = metrics.get("improvement_over_baseline_pct")
        if dir_acc is None:
            return 50.0
        score = 50.0 + max(-25.0, min(30.0, float(dir_acc) - 50.0))
        if improvement is not None:
            score += max(-10.0, min(8.0, float(improvement) * 0.5))
        return round(max(5.0, min(95.0, score)), 1)


ml_service = LSTMPredictionEngine()
