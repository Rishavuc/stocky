"""Reproducible chronological baseline/boosting/LSTM comparison.
Validation chooses the model; the untouched final test estimates performance.
Targets and preprocessing are separated by a horizon-sized purge gap.
"""

import json, hashlib, random, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
import joblib, sklearn
from app.market import ROOT, DATA, catalog


class LSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.recurrent = nn.LSTM(1, 24, batch_first=True)
        self.head = nn.Linear(24, 1)

    def forward(self, x):
        out, _ = self.recurrent(x)
        return self.head(out[:, -1]).squeeze(-1)


def train(symbol, horizon, epochs=30):
    torch.set_num_threads(2)
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    df = pd.read_csv(DATA / f"{symbol}.csv")
    c = df.close.to_numpy(float)
    returns = np.diff(np.log(c))
    window = 30
    indices = np.arange(window, len(c) - horizon)
    X = np.array([returns[i - window : i] for i in indices])
    y = np.array([np.log(c[i + horizon] / c[i]) for i in indices])
    a = int(len(X) * 0.65)
    b = int(len(X) * 0.82)
    tr = np.arange(0, a - horizon)
    va = np.arange(a, b - horizon)
    te = np.arange(b, len(X))
    scaler = StandardScaler().fit(X[tr])
    xs = scaler.transform(X).astype("float32")
    ymean = float(y[tr].mean())
    ystd = float(y[tr].std()) or 1
    target = ((y - ymean) / ystd).astype("float32")
    boost = HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=12, l2_regularization=3, random_state=42
    ).fit(xs[tr], y[tr])
    model = LSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.008)
    criterion = nn.MSELoss()
    tx = torch.tensor(xs[tr, :, None])
    ty = torch.tensor(target[tr])
    best = float("inf")
    best_state = None
    best_epoch = 0
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = criterion(model(tx), ty)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1)
        optimizer.step()
        model.eval()
        with torch.no_grad():
            vloss = criterion(
                model(torch.tensor(xs[va, :, None])), torch.tensor(target[va])
            ).item()
        if vloss < best:
            best = vloss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch + 1
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        lstm = model(torch.tensor(xs[:, :, None])).numpy() * ystd + ymean
    predictions = {
        "Last-price baseline": np.zeros(len(X)),
        "Gradient boosting": boost.predict(xs),
        "LSTM": lstm,
    }
    actual = c[indices + horizon]
    base = c[indices]

    def metrics(pred, subset):
        estimated = base[subset] * np.exp(pred[subset])
        truth = actual[subset]
        err = estimated - truth
        # Long or cash decision, entry at next open, exit at horizon close.
        idx = indices[subset]
        entry = df.open.to_numpy(float)[idx + 1]
        real_return = truth / entry - 1
        positions = (pred[subset] > 0).astype(float)
        strategy = positions * (real_return - 0.001)
        # Non-overlapping samples avoid counting overlapping horizons as a portfolio.
        realized = strategy[::horizon]
        curve = np.cumprod(1 + realized)
        peak = np.maximum.accumulate(np.r_[1.0, curve])[1:]
        return {
            "mae": round(float(np.abs(err).mean()), 4),
            "rmse": round(float(np.sqrt((err**2).mean())), 4),
            "directional_accuracy_pct": round(
                float((np.sign(pred[subset]) == np.sign(y[subset])).mean() * 100), 2
            ),
            "strategy_return_pct": round(float((curve[-1] - 1) * 100), 2),
            "max_drawdown_pct": round(float(np.min(curve / peak - 1) * 100), 2),
            "test_trades": int(positions[::horizon].sum()),
        }

    val = {k: metrics(v, va) for k, v in predictions.items()}
    selected = min(val, key=lambda k: val[k]["mae"])
    test = {k: metrics(v, te) for k, v in predictions.items()}
    residual = np.abs(actual[va] / base[va] - np.exp(predictions[selected][va]))
    radius = float(np.quantile(residual, 0.9, method="higher"))
    coverage = float(
        (
            np.abs(actual[te] / base[te] - np.exp(predictions[selected][te])) <= radius
        ).mean()
        * 100
    )
    latest_x = scaler.transform(returns[-window:][None]).astype("float32")
    with torch.no_grad():
        lr = float(model(torch.tensor(latest_x[:, :, None])).item() * ystd + ymean)
    live_preds = {
        "Last-price baseline": 0.0,
        "Gradient boosting": float(boost.predict(latest_x)[0]),
        "LSTM": lr,
    }
    target_price = float(c[-1] * np.exp(live_preds[selected]))
    checksum = hashlib.sha256((DATA / f"{symbol}.csv").read_bytes()).hexdigest()
    recipe = hashlib.sha256(
        (
            Path(__file__).read_text()
            + str(torch.__version__)
            + sklearn.__version__
            + str(epochs)
        ).encode()
    ).hexdigest()[:8]
    version = f"{symbol}-{horizon}d-{checksum[:10]}-{recipe}-seed42"
    dates = df.date.to_numpy()
    report = {
        "symbol": symbol,
        "horizon_sessions": horizon,
        "version": version,
        "selected_model": selected,
        "selection_rule": "Lowest validation price MAE, before examining final test",
        "data_sha256": checksum,
        "as_of": str(dates[-1]),
        "current_price": round(float(c[-1]), 2),
        "predicted_target": round(target_price, 2),
        "expected_return_pct": round((target_price / c[-1] - 1) * 100, 2),
        "status": "Historical research forecast; not a current executable quote",
        "interval": {
            "lower": round(max(0, target_price - c[-1] * radius), 2),
            "upper": round(target_price + c[-1] * radius, 2),
            "method": "Symmetric absolute relative-price residual quantile, calibrated on validation observations",
            "nominal_coverage_pct": 90,
            "test_coverage_pct": round(coverage, 2),
            "caveat": "Empirical coverage, not a guaranteed probability; overlapping and dependent market observations weaken calibration assumptions.",
        },
        "validation": val,
        "test": test,
        "beats_baseline": test[selected]["mae"] < test["Last-price baseline"]["mae"],
        "split": {
            "train_start": str(dates[indices[tr[0]]]),
            "train_end": str(dates[indices[tr[-1]] + horizon]),
            "validation_start": str(dates[indices[va[0]]]),
            "validation_end": str(dates[indices[va[-1]] + horizon]),
            "test_start": str(dates[indices[te[0]]]),
            "test_end": str(dates[indices[te[-1]] + horizon]),
            "train_samples": len(tr),
            "validation_samples": len(va),
            "test_samples": len(te),
            "purge_sessions": horizon,
        },
        "training": {
            "libraries": {
                "torch": str(torch.__version__),
                "numpy": np.__version__,
                "sklearn": sklearn.__version__,
            },
            "seed": 42,
            "window_sessions": window,
            "lstm_hidden_units": 24,
            "epochs": epochs,
            "best_epoch": best_epoch,
            "features": "30 preceding daily log returns; scaler fitted only to training observations",
            "target": "Log close-to-close return over the forecast horizon",
        },
        "strategy_assumptions": "Long or cash, signal after session close, enter next open, exit horizon close; non-overlapping test decisions; 0.10% round-trip cost per trade. No leverage, slippage model, or total-return corporate-action adjustment. Baseline predicts zero return and stays in cash.",
        "test_points": [
            {
                "date": str(dates[indices[j] + horizon]),
                "actual": round(float(actual[j]), 2),
                "prediction": round(
                    float(base[j] * np.exp(predictions[selected][j])), 2
                ),
                "baseline": round(float(base[j]), 2),
            }
            for j in te
        ],
        "notes": [
            "An educational experiment, not evidence of reliable trading profits.",
            "Latest inference is dated to the bundled dataset end.",
            "Replay never calls this model: its training window could include future replay observations.",
        ],
    }
    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": boost,
            "scaler": scaler,
            "ymean": ymean,
            "ystd": ystd,
            "version": version,
        },
        out / f"{symbol}_{horizon}.joblib",
    )
    torch.save(
        {"state_dict": model.state_dict(), "version": version},
        out / f"{symbol}_{horizon}.pt",
    )
    (out / f"{symbol}_{horizon}_report.json").write_text(json.dumps(report, indent=2))
    print(
        symbol,
        horizon,
        selected,
        "test MAE",
        test[selected]["mae"],
        "baseline",
        test["Last-price baseline"]["mae"],
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol")
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()
    for row in catalog():
        if args.symbol and row["symbol"] != args.symbol:
            continue
        for h in (1, 5):
            train(row["symbol"], h, args.epochs)
