"""Market comparison, saved research layouts and named watchlists."""
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException
from app import market, trading
from app.store import now

class ComparisonRequest(BaseModel):
    symbols:list[str]=Field(min_length=2,max_length=4)
    observations:int=Field(default=252,ge=20,le=1260)
class ChartLayout(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    symbol:str
    observations:int=Field(default=180,ge=30,le=2000)
    overlays:list[str]=Field(default_factory=list,max_length=4)
    chart_type:str='candles'
class WatchlistRequest(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    symbols:list[str]=Field(default_factory=list,max_length=100)

def risk_summary(rows, sessions_per_year=252):
    df=pd.DataFrame(rows)
    if len(df)<3:return {'status':'insufficient_history'}
    prices=df.close.to_numpy(float);returns=np.diff(prices)/prices[:-1]
    intraday='T' in str(df.date.iloc[0]);annualization=None if intraday else sessions_per_year
    peak=np.maximum.accumulate(prices);drawdown=(prices/peak-1)*100
    start=pd.Timestamp(df.date.iloc[0]);end=pd.Timestamp(df.date.iloc[-1]);days=(end-start).total_seconds()/86400
    volatility=float(np.std(returns,ddof=1))
    result={'observations':len(rows),'start':str(df.date.iloc[0]),'end':str(df.date.iloc[-1]),'return_pct':float((prices[-1]/prices[0]-1)*100),'max_drawdown_pct':float(drawdown.min()),'positive_observations_pct':float((returns>0).mean()*100),'annualized_volatility_pct':float(volatility*np.sqrt(annualization)*100) if annualization else None,'sharpe_zero_rf':float(returns.mean()/volatility*np.sqrt(annualization)) if annualization and volatility>0 else None,'cagr_pct':float(((prices[-1]/prices[0])**(365.25/days)-1)*100) if days>=365 else None,'assumptions':f'Daily metrics annualize with {sessions_per_year} observations and assume a zero risk-free rate. Price/NAV returns exclude additional taxes, exit loads and currency conversion. Intraday statistics are not annualized.'}
    return result

def compare(symbols,observations):
    if len(set(symbols))!=len(symbols):raise HTTPException(422,'Choose distinct instruments')
    histories={symbol:market.history(symbol)[-observations:] for symbol in symbols}
    # Compare dates actually observed by every source; never fabricate missing dates.
    common=sorted(set.intersection(*[{r['date'] for r in rows} for rows in histories.values()]))
    if len(common)<2:raise HTTPException(422,'These instruments do not have enough common observation timestamps. Compare matching timeframes.')
    result=[];aligned={}
    for symbol,rows in histories.items():
        mapping={r['date']:r for r in rows};observed=[mapping[d] for d in common];prices=np.array([r['close'] for r in observed]);normalized=prices/prices[0]*100
        aligned[symbol]=pd.Series(np.diff(prices)/prices[:-1],index=common[1:])
        m=market.meta(symbol)
        result.append({'symbol':symbol,'name':m['name'],'currency':m['currency'],'source':m['source'],'as_of':common[-1],'points':[{'date':d,'value':float(v)} for d,v in zip(common,normalized)],'metrics':risk_summary(observed, sessions_per_year=365 if m.get('segment')=='crypto' else 252)})
    correlations=pd.DataFrame(aligned).corr()
    return {'instruments':result,'correlation':{a:{b:None if pd.isna(correlations.loc[a,b]) else float(correlations.loc[a,b]) for b in symbols} for a in symbols},'shared_observations':len(common),'start':common[0],'end':common[-1],'note':'All series start at 100 on the first common observation. Native-currency percentage changes are compared; no FX-adjusted investment return is implied.'}

def option_summary(chain):
    rows=[]
    for item in chain:
        strike=float(item['strike_price']);call=item.get('call_options',{}).get('market_data',{});put=item.get('put_options',{}).get('market_data',{})
        rows.append({'strike':strike,'call_oi':call.get('oi'),'put_oi':put.get('oi'),'call_change_oi':float(call['oi'])-float(call['prev_oi']) if call.get('oi') is not None and call.get('prev_oi') is not None else None,'put_change_oi':float(put['oi'])-float(put['prev_oi']) if put.get('oi') is not None and put.get('prev_oi') is not None else None})
    complete=bool(rows) and all(r['call_oi'] is not None and r['put_oi'] is not None for r in rows)
    if not complete:return {'status':'incomplete_open_interest','strikes':rows,'max_pain':None}
    payouts=[(sum(max(candidate['strike']-r['strike'],0)*float(r['call_oi'])+max(r['strike']-candidate['strike'],0)*float(r['put_oi']) for r in rows),candidate['strike']) for candidate in rows]
    return {'status':'calculated','max_pain':min(payouts)[1],'largest_call_oi_strike':max(rows,key=lambda r:float(r['call_oi']))['strike'],'largest_put_oi_strike':max(rows,key=lambda r:float(r['put_oi']))['strike'],'total_call_oi':sum(float(r['call_oi']) for r in rows),'total_put_oi':sum(float(r['put_oi']) for r in rows),'strikes':rows,'note':'Max pain minimizes intrinsic payout using observed open interest for the returned strikes. It is a snapshot calculation, not a price forecast. Missing prior OI remains unavailable.'}

def install(app):
    from app.main import current,database
    db_dep=Depends(database,scope='function')
    @app.post('/v1/analysis/comparison')
    def comparison(req:ComparisonRequest):return compare(req.symbols,req.observations)
    @app.get('/v1/research/layouts')
    def layouts(u=Depends(current),db=db_dep):return [{'id':r.key,**r.data} for r in trading.records(db,u.id,'chart_layout')]
    @app.post('/v1/research/layouts')
    def save_layout(req:ChartLayout,u=Depends(current),db=db_dep):
        if not req.name.strip():raise HTTPException(422,'Layout name cannot be blank')
        market.meta(req.symbol)
        if req.chart_type not in ('candles','line') or any(x not in ('SMA20','EMA20','BOLLINGER') for x in req.overlays):raise HTTPException(422,'Unsupported chart configuration')
        key=trading.ident();trading.put(db,u.id,'chart_layout',key,{**req.model_dump(),'created_at':now()});return {'id':key}
    @app.delete('/v1/research/layouts/{key}')
    def delete_layout(key:str,u=Depends(current),db=db_dep):
        r=trading.get(db,u.id,'chart_layout',key)
        if not r:raise HTTPException(404,'Layout not found')
        db.delete(r);return {'deleted':True}
    @app.get('/v1/watchlists')
    def watchlists(u=Depends(current),db=db_dep):return [{'id':r.key,**r.data} for r in trading.records(db,u.id,'named_watchlist')]
    @app.post('/v1/watchlists')
    def create_watchlist(req:WatchlistRequest,u=Depends(current),db=db_dep):
        if not req.name.strip():raise HTTPException(422,'Watchlist name cannot be blank')
        for symbol in req.symbols:market.meta(symbol)
        key=trading.ident();r=trading.put(db,u.id,'named_watchlist',key,{'name':req.name.strip(),'symbols':list(dict.fromkeys(req.symbols)),'updated_at':now()});return {'id':key,**r.data}
    @app.put('/v1/watchlists/{key}')
    def update_watchlist(key:str,req:WatchlistRequest,u=Depends(current),db=db_dep):
        r=trading.get(db,u.id,'named_watchlist',key)
        if not r:raise HTTPException(404,'Watchlist not found')
        if not req.name.strip():raise HTTPException(422,'Watchlist name cannot be blank')
        for symbol in req.symbols:market.meta(symbol)
        r.data={'name':req.name.strip(),'symbols':list(dict.fromkeys(req.symbols)),'updated_at':now()};return {'id':key,**r.data}
    @app.delete('/v1/watchlists/{key}')
    def remove_watchlist(key:str,u=Depends(current),db=db_dep):
        r=trading.get(db,u.id,'named_watchlist',key)
        if not r:raise HTTPException(404,'Watchlist not found')
        db.delete(r);return {'deleted':True}
