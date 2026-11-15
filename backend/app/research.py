"""Expanding chronological folds, quantile LSTM, persisted runs and later outcomes."""

import json, hashlib, random, argparse, io
from pathlib import Path
import numpy as np, pandas as pd, torch, joblib, sklearn
from torch import nn
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor
from app import market
from app.datasets import atomic, read
from app.store import DB, init, now
from app import trading

ROOT = market.ROOT


class QuantileLSTM(nn.Module):
    def __init__(self, input_size=3):
        super().__init__()
        self.rnn = nn.LSTM(input_size, 24, batch_first=True)
        self.head = nn.Linear(24, 3)

    def forward(self, x):
        y, _ = self.rnn(x)
        return torch.sort(self.head(y[:, -1]), dim=1).values


def feature_matrix(df, symbol, count=4):
    close = df.close.to_numpy(float)
    returns = np.r_[0, np.diff(np.log(close))]
    volume = np.log1p(df.volume.to_numpy(float))
    volatility = (
        pd.Series(returns).rolling(10, min_periods=1).std().fillna(0).to_numpy()
    )
    base = np.column_stack((returns, volume, volatility))
    if count == 3:
        return base, None
    metadata = market.meta(symbol)
    reference = (
        ("BTCUSDT_1h" if metadata.get("timeframe") == "1h" else "BTCUSDT")
        if metadata.get("segment") == "crypto"
        else "NIFTY50"
    )
    context_metadata = market.meta(reference)
    rows = pd.DataFrame(market.history(reference))
    values = np.r_[0, np.diff(np.log(rows.close.to_numpy(float)))]
    stamps = pd.to_datetime(rows.date, utc=True)
    if reference == "NIFTY50":
        stamps = stamps + pd.Timedelta(
            hours=10
        )  # Date-only index bar is usable after 15:30 IST.
    right = pd.DataFrame({"stamp": stamps, "context": values}).sort_values("stamp")
    left = pd.DataFrame(
        {"stamp": pd.to_datetime(df.date, utc=True), "order": np.arange(len(df))}
    ).sort_values("stamp")
    joined = pd.merge_asof(
        left, right, on="stamp", direction="backward", allow_exact_matches=False
    ).sort_values("order")
    # Missing initial context is an explicit feature imputation, never an invented quote.
    context_values = joined.context.fillna(0).to_numpy()
    return np.column_stack((base, context_values)), {
        "symbol": reference,
        "dataset_version": context_metadata["sha256"],
        "join": "Strictly earlier observed bar; initial unavailable context is zero-imputed",
    }


def train(symbol, horizon, epochs=15):
    torch.set_num_threads(2)
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)
    content = read(symbol)
    df = pd.read_csv(io.BytesIO(content)).tail(4000).reset_index(drop=True)
    if len(df) < 350:
        return None
    close = df.close.to_numpy(float)
    ret = np.r_[0, np.diff(np.log(close))]
    volume = np.log1p(df.volume.to_numpy(float))
    vol = pd.Series(ret).rolling(10, min_periods=1).std().fillna(0).to_numpy()
    features, context = feature_matrix(df, symbol)
    window = 30
    indices = np.arange(window, len(df) - horizon)
    X = np.array([features[i - window + 1 : i + 1] for i in indices])
    y = np.log(close[indices + horizon] / close[indices])
    base = close[indices]
    actual = close[indices + horizon]
    quantiles = np.array([0.1, 0.5, 0.9])
    folds = []

    def metrics(pred, part, lo=None, hi=None):
        estimate = base[part] * np.exp(pred[part])
        err = estimate - actual[part]
        idx = indices[part]
        entry = df.open.to_numpy(float)[idx + 1]
        positions = pred[part] > 0
        r = (positions * (actual[part] / entry - 1 - 0.001))[::horizon]
        curve = np.cumprod(1 + r)
        peak = np.maximum.accumulate(np.r_[1, curve])[1:]
        return {
            "mae": round(float(abs(err).mean()), 4),
            "rmse": round(float(np.sqrt((err * err).mean())), 4),
            "directional_accuracy_pct": round(
                float((np.sign(pred[part]) == np.sign(y[part])).mean() * 100), 2
            ),
            "strategy_return_pct": round(float((curve[-1] - 1) * 100), 2),
            "max_drawdown_pct": round(float((curve / peak - 1).min() * 100), 2),
            "test_trades": int(positions[::horizon].sum()),
        }

    for fold, (a, b, c) in enumerate(
        ((0.45, 0.55, 0.65), (0.60, 0.70, 0.80), (0.75, 0.85, 1.0))
    ):
        ai = int(len(X) * a)
        bi = int(len(X) * b)
        ci = int(len(X) * c)
        tr = np.arange(0, ai - horizon)
        va = np.arange(ai, bi - horizon)
        te = np.arange(bi, ci)
        scaler = StandardScaler().fit(X[tr].reshape(-1, features.shape[1]))
        scaled = (
            scaler.transform(X.reshape(-1, features.shape[1]))
            .reshape(X.shape)
            .astype("float32")
        )
        flat = scaled.reshape(len(X), -1)
        mean = float(y[tr].mean())
        std = float(y[tr].std()) or 1.0
        target = ((y - mean) / std).astype("float32")
        model = QuantileLSTM(features.shape[1])
        opt = torch.optim.Adam(model.parameters(), lr=0.007)
        best = float("inf")
        state = None
        qs = torch.tensor(quantiles, dtype=torch.float32)

        def loss(out, target):
            delta = target[:, None] - out
            return torch.maximum(qs * delta, (qs - 1) * delta).mean()

        for epoch in range(epochs):
            model.train()
            opt.zero_grad()
            v = loss(model(torch.tensor(scaled[tr])), torch.tensor(target[tr]))
            v.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1)
            opt.step()
            model.eval()
            with torch.no_grad():
                vl = loss(
                    model(torch.tensor(scaled[va])), torch.tensor(target[va])
                ).item()
            if vl < best:
                best = vl
                state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        model.load_state_dict(state)
        model.eval()
        with torch.no_grad():
            lstm = model(torch.tensor(scaled)).numpy() * std + mean
        boost = HistGradientBoostingRegressor(
            max_iter=80, max_leaf_nodes=10, l2_regularization=3, random_state=42
        ).fit(flat[tr], y[tr])
        moving = np.array(
            [np.log(close[max(0, i - 4) : i + 1].mean() / close[i]) for i in indices]
        )
        preds = {
            "Last-price baseline": np.zeros(len(X)),
            "Moving-average baseline": moving,
            "Gradient boosting": boost.predict(flat),
            "LSTM": lstm[:, 1],
        }
        val = {k: metrics(v, va) for k, v in preds.items()}
        selected = min(val, key=lambda k: val[k]["mae"])
        test = {k: metrics(v, te) for k, v in preds.items()}
        folds.append(
            {
                "fold": fold + 1,
                "train_end": str(df.date.iloc[indices[tr[-1]] + horizon]),
                "validation_start": str(df.date.iloc[indices[va[0]]]),
                "test_start": str(df.date.iloc[indices[te[0]]]),
                "test_end": str(df.date.iloc[indices[te[-1]] + horizon]),
                "selected_model": selected,
                "validation": val,
                "test": test,
            }
        )
    latest = scaler.transform(features[-window:]).astype("float32")[None]
    with torch.no_grad():
        lq = model(torch.tensor(latest)).numpy()[0] * std + mean
    latest_pred = {
        "Last-price baseline": 0.0,
        "Moving-average baseline": float(np.log(close[-5:].mean() / close[-1])),
        "Gradient boosting": float(boost.predict(latest.reshape(1, -1))[0]),
        "LSTM": float(lq[1]),
    }
    if selected == "LSTM":
        low, high = lq[0], lq[2]
        test_low = lstm[te, 0]
        test_high = lstm[te, 2]
        method = "LSTM 0.1/0.5/0.9 return quantiles trained with pinball loss"
    else:
        residual = y[va] - preds[selected][va]
        ql, qh = np.quantile(residual, [0.1, 0.9])
        low = latest_pred[selected] + ql
        high = latest_pred[selected] + qh
        test_low = preds[selected][te] + ql
        test_high = preds[selected][te] + qh
        method = "Validation residual quantiles around the selected baseline/boosting prediction"
    coverage = float(((y[te] >= test_low) & (y[te] <= test_high)).mean() * 100)
    digest = hashlib.sha256(content).hexdigest()
    recipe = hashlib.sha256(
        (Path(__file__).read_text() + str(epochs) + str(torch.__version__)).encode()
    ).hexdigest()[:8]
    version = f"{symbol}-{horizon}d-{digest[:10]}-{recipe}-seed42"
    asof = str(df.date.iloc[-1])
    target_price = close[-1] * np.exp(latest_pred[selected])
    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    report = {
        "symbol": symbol,
        "currency": market.meta(symbol)["currency"],
        "horizon_sessions": horizon,
        "version": version,
        "selected_model": selected,
        "selection_rule": "Latest expanding fold validation MAE; all three later test folds retained",
        "data_sha256": digest,
        "as_of": asof,
        "current_price": round(float(close[-1]), 2),
        "predicted_target": round(float(target_price), 2),
        "expected_return_pct": round(float((target_price / close[-1] - 1) * 100), 2),
        "status": "qualified"
        if all(
            f["test"][f["selected_model"]]["mae"]
            < f["test"]["Last-price baseline"]["mae"]
            for f in folds
        )
        else "experimental",
        "beats_baseline": test[selected]["mae"] < test["Last-price baseline"]["mae"],
        "interval": {
            "lower": round(float(close[-1] * np.exp(low)), 2),
            "upper": round(float(close[-1] * np.exp(high)), 2),
            "method": method,
            "nominal_coverage_pct": 80,
            "test_coverage_pct": round(coverage, 2),
            "caveat": "Empirical coverage on later observations, not a guaranteed probability.",
        },
        "validation": val,
        "test": test,
        "folds": folds,
        "split": {
            "train_start": str(df.date.iloc[indices[tr[0]]]),
            "train_end": str(df.date.iloc[indices[tr[-1]] + horizon]),
            "validation_start": str(df.date.iloc[indices[va[0]]]),
            "validation_end": str(df.date.iloc[indices[va[-1]] + horizon]),
            "test_start": str(df.date.iloc[indices[te[0]]]),
            "test_end": str(df.date.iloc[indices[te[-1]] + horizon]),
            "train_samples": len(tr),
            "validation_samples": len(va),
            "test_samples": len(te),
            "purge_sessions": horizon,
        },
        "training": {
            "seed": 42,
            "window_sessions": window,
            "features": "Log returns, log volume, trailing volatility and strictly earlier Nifty/Bitcoin returns. Scaling fitted within each fold; maximum 4000 observed bars.",
            "context": context,
            "epochs": epochs,
            "libraries": {
                "torch": str(torch.__version__),
                "numpy": np.__version__,
                "sklearn": sklearn.__version__,
            },
        },
        "strategy_assumptions": "Long or cash; decide after close, enter next open, exit horizon close; non-overlapping decisions; 0.10% round-trip cost. No leverage or total-return adjustment.",
        "test_points": [
            {
                "date": str(df.date.iloc[indices[j] + horizon]),
                "actual": round(float(actual[j]), 2),
                "prediction": round(float(base[j] * np.exp(preds[selected][j])), 2),
                "baseline": round(float(base[j]), 2),
            }
            for j in te
        ],
        "notes": [
            "Research forecasts are not used inside replay if trained on later observations.",
            "Qualification is separate from visibility: weak experiments remain available for learning.",
            "Inputs use observed bars; no missing prices or market-context factors are fabricated.",
        ],
    }
    artifact = out / "runs" / version
    artifact.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": boost,
            "scaler": scaler,
            "mean": mean,
            "std": std,
            "version": version,
            "feature_count": features.shape[1],
        },
        artifact / "boost.joblib",
    )
    torch.save(
        {"state_dict": model.state_dict(), "version": version}, artifact / "lstm.pt"
    )
    atomic(artifact / "report.json", json.dumps(report, indent=2))
    atomic(out / f"{symbol}_{horizon}_report.json", json.dumps(report, indent=2))
    with DB.begin() as db:
        trading.put(
            db,
            "system",
            "model_run",
            version,
            {
                "version": version,
                "symbol": symbol,
                "horizon": horizon,
                "as_of": asof,
                "status": report["status"],
                "data_version": digest,
                "created_at": now(),
            },
        )
        pid = version + ":" + asof
        trading.put(
            db,
            "system",
            "prediction",
            pid,
            {
                "id": pid,
                "symbol": symbol,
                "version": version,
                "dataset_version": digest,
                "as_of": asof,
                "horizon": horizon,
                "current_price": float(close[-1]),
                "predicted": float(target_price),
                "status": "pending",
                "created_at": now(),
            },
        )
    print(symbol, horizon, selected, report["status"], flush=True)
    return report


def outcomes():
    with DB.begin() as db:
        for r in trading.records(db, "system", "prediction"):
            p = r.data
            if p["status"] != "pending":
                continue
            rows = market.history(p["symbol"])
            index = next(
                (i for i, x in enumerate(rows) if x["date"] == p["as_of"]), None
            )
            if index is not None and index + p["horizon"] < len(rows):
                actual = rows[index + p["horizon"]]["close"]
                r.data = {
                    **p,
                    "status": "observed",
                    "actual": actual,
                    "actual_at": rows[index + p["horizon"]]["date"],
                    "absolute_error": abs(actual - p["predicted"]),
                    "baseline_error": abs(actual - p["current_price"]),
                }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(
        ROOT / ".env"
    )  # CLI callers should export DATABASE_URL before module import.
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol")
    parser.add_argument("--epochs", type=int, default=15)
    args = parser.parse_args()
    init()
    for m in market.catalog():
        if args.symbol and m["symbol"] != args.symbol:
            continue
        segment = m.get("segment", "equities")
        horizons = (
            (21,)
            if segment == "funds"
            else (3,)
            if segment == "intraday"
            else (1, 24)
            if segment == "crypto"
            else (1, 5)
        )
        for horizon in horizons:
            train(m["symbol"], horizon, args.epochs)
    outcomes()


def infer(symbol, horizon):
    """Infer from saved preprocessing/weights; never fit on the new observations."""
    torch.set_num_threads(2)
    path = ROOT / "models" / f"{symbol}_{horizon}_report.json"
    if not path.exists():
        return None
    previous = json.loads(path.read_text())
    artifact = ROOT / "models/runs" / previous["version"]
    if not (artifact / "boost.joblib").exists():
        return None
    trained = json.loads((artifact / "report.json").read_text())
    content = read(symbol)
    df = pd.read_csv(io.BytesIO(content))
    asof = str(df.date.iloc[-1])
    if (
        asof == previous["as_of"]
        and previous["data_sha256"] == hashlib.sha256(content).hexdigest()
    ):
        return previous
    state = joblib.load(artifact / "boost.joblib")
    close = df.close.to_numpy(float)
    ret = np.r_[0, np.diff(np.log(close))]
    volume = np.log1p(df.volume.to_numpy(float))
    vol = pd.Series(ret).rolling(10, min_periods=1).std().fillna(0).to_numpy()
    features, context = feature_matrix(df, symbol, state.get("feature_count", 3))
    latest = state["scaler"].transform(features[-30:]).astype("float32")[None]
    selected = trained["selected_model"]
    if selected == "LSTM":
        model = QuantileLSTM(latest.shape[2])
        saved = torch.load(artifact / "lstm.pt", map_location="cpu", weights_only=True)
        model.load_state_dict(saved["state_dict"])
        model.eval()
        with torch.no_grad():
            q = model(torch.tensor(latest)).numpy()[0] * state["std"] + state["mean"]
        low, pred, high = q
    else:
        pred = (
            0.0
            if selected == "Last-price baseline"
            else float(np.log(close[-5:].mean() / close[-1]))
            if selected == "Moving-average baseline"
            else float(state["model"].predict(latest.reshape(1, -1))[0])
        )
        oldpred = np.log(trained["predicted_target"] / trained["current_price"])
        low = (
            pred
            + np.log(trained["interval"]["lower"] / trained["current_price"])
            - oldpred
        )
        high = (
            pred
            + np.log(trained["interval"]["upper"] / trained["current_price"])
            - oldpred
        )
    digest = hashlib.sha256(content).hexdigest()
    target = float(close[-1] * np.exp(pred))
    report = {
        **trained,
        "trained_data_sha256": trained["data_sha256"],
        "data_sha256": digest,
        "inference_at": now(),
        "as_of": asof,
        "current_price": round(float(close[-1]), 2),
        "predicted_target": round(target, 2),
        "expected_return_pct": round(float((target / close[-1] - 1) * 100), 2),
        "interval": {
            **trained["interval"],
            "lower": round(float(close[-1] * np.exp(low)), 2),
            "upper": round(float(close[-1] * np.exp(high)), 2),
        },
    }
    atomic(path, json.dumps(report, indent=2))
    with DB.begin() as db:
        pid = trained["version"] + ":" + asof
        trading.put(
            db,
            "system",
            "prediction",
            pid,
            {
                "id": pid,
                "symbol": symbol,
                "version": trained["version"],
                "dataset_version": digest,
                "as_of": asof,
                "horizon": horizon,
                "current_price": float(close[-1]),
                "predicted": target,
                "status": "pending",
                "created_at": now(),
            },
        )
    return report
