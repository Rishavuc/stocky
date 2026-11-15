"""Segment-specific analysis of recorded observations, without synthetic feeds."""
import math
import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app import market, trading
from app.store import now

class ImportPreset(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    broker: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,40}$')
    mapping: dict[str, str] = Field(max_length=8)


def crypto_analysis(symbol):
    from app.workbench import risk_summary
    meta = market.meta(symbol)
    if meta.get('segment') != 'crypto':
        raise HTTPException(422, 'Choose a crypto instrument')
    rows = market.history(symbol)
    prices = np.array([r['close'] for r in rows], dtype=float)
    timeframe = meta.get('timeframe', '1d')
    steps = 24 if timeframe == '1h' else 1
    result = {
        'symbol': symbol, 'name': meta['name'], 'currency': meta['currency'],
        'source': meta['source'], 'as_of': rows[-1]['date'],
        'dataset_version': meta.get('sha256'), 'timeframe': timeframe,
        'price': float(prices[-1]), 'status': 'recorded_observations',
        'risk': risk_summary(rows[-366:], sessions_per_year=365),
        'returns': {}, 'window_24h': None, 'bitcoin_correlation': None,
        'unavailable': ['Market capitalization', 'Funding rates', 'On-chain activity'],
        'note': 'Statistics use completed recorded candles, not a current ticker. Volume is base-asset units from the source, not quote-currency turnover. No INR conversion or real-money execution is implied.'
    }
    for label, n in [('24 hours', steps), ('7 days', steps * 7), ('30 days', steps * 30)]:
        if len(rows) <= n:
            continue
        elapsed = (pd.Timestamp(rows[-1]['date'])-pd.Timestamp(rows[-n-1]['date'])).total_seconds()
        expected = n * (3600 if timeframe == '1h' else 86400)
        if elapsed == expected:
            result['returns'][label] = float((prices[-1]/prices[-n-1]-1)*100)
    if '24 hours' in result['returns']:
        window = rows[-steps:]
        result['window_24h'] = {
            'start': rows[-steps-1]['date'], 'end': rows[-1]['date'],
            'high': max(r['high'] for r in window), 'low': min(r['low'] for r in window),
            'base_volume': sum(r['volume'] for r in window),
        }
    benchmark = 'BTCUSDT_1h' if timeframe == '1h' else ('BTCUSD' if meta['currency'] == 'USD' else 'BTCUSDT')
    if symbol != benchmark:
        own = pd.Series({r['date']: r['close'] for r in rows[-181:]})
        btc = pd.Series({r['date']: r['close'] for r in market.history(benchmark)[-181:]})
        aligned = pd.concat([own.rename('asset'), btc.rename('bitcoin')], axis=1).dropna().pct_change().dropna()
        if len(aligned) >= 20:
            corr = float(aligned.asset.corr(aligned.bitcoin))
            if math.isfinite(corr):
                result['bitcoin_correlation'] = {'symbol': benchmark, 'value': corr, 'matched_returns': len(aligned), 'start': str(aligned.index[0]), 'end': str(aligned.index[-1])}
    return result


def rolling_fund(symbol, window):
    meta = market.meta(symbol)
    if meta.get('segment') != 'funds':
        raise HTTPException(422, 'Choose a mutual-fund instrument')
    rows = market.history(symbol)
    if len(rows) <= window:
        raise HTTPException(422, 'Not enough NAV observations for this rolling window')
    prices = np.array([r['close'] for r in rows], dtype=float)
    returns = (prices[window:]/prices[:-window]-1)*100
    points = [{'date': rows[i+window]['date'], 'value': float(v)} for i, v in enumerate(returns)]
    return {
        'symbol': symbol, 'window': window, 'source': meta['source'], 'as_of': rows[-1]['date'],
        'points': points, 'minimum_pct': float(returns.min()), 'median_pct': float(np.median(returns)),
        'maximum_pct': float(returns.max()), 'positive_windows_pct': float((returns>0).mean()*100),
        'windows': len(points),
        'note': 'Each point is the cumulative NAV return over the preceding chosen number of published observations, not calendar days. Overlapping windows are not independent. Returns exclude exit loads and investor taxes.'
    }


def install(app):
    from app.main import current, database
    dep = Depends(database, scope='function')

    @app.get('/v1/analysis/crypto/{symbol}')
    def crypto(symbol: str):
        return crypto_analysis(symbol)

    @app.get('/v1/analysis/funds/{symbol}/rolling')
    def rolling(symbol: str, window: int = Query(default=252, ge=21, le=756)):
        return rolling_fund(symbol, window)

    @app.get('/v1/imports/presets')
    def presets(u=Depends(current), db=dep):
        return [{'id': r.key, **r.data} for r in trading.records(db, u.id, 'import_preset')]

    @app.post('/v1/imports/presets')
    def save_preset(req: ImportPreset, u=Depends(current), db=dep):
        allowed = {'external_id','symbol','side','qty','price','fees','executed_at','currency'}
        if not req.name.strip() or set(req.mapping)-allowed or any(len(v)>200 for v in req.mapping.values()):
            raise HTTPException(422, 'Provide a name and supported column mappings')
        key = trading.ident()
        r = trading.put(db, u.id, 'import_preset', key, {**req.model_dump(), 'name': req.name.strip(), 'saved_at': now()})
        return {'id': key, **r.data}

    @app.delete('/v1/imports/presets/{key}')
    def remove_preset(key: str, u=Depends(current), db=dep):
        r = trading.get(db, u.id, 'import_preset', key)
        if not r:
            raise HTTPException(404, 'Import preset not found')
        db.delete(r)
        return {'deleted': True}
