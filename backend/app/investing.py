"""Shared provider instrument identities for live research, watchlists and alerts."""
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd
from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from app import trading, market
from app.store import Observation, now
from app import live
from app.indicators import range_indicators


def identify(provider, symbol, exchange=None):
    return f'{provider}:{exchange or ("spot" if provider=="binance" else "NSE")}:{symbol}'


def instrument(db, owner, identity):
    parts=identity.split(':',2)
    if len(parts)!=3:raise HTTPException(422,'Choose an instrument returned by live search')
    provider,exchange,symbol=parts
    if provider=='binance' and exchange=='spot':
        catalog=trading.get(db,'public','live_feed','binance_catalog')
        rows=catalog.data['instruments'] if catalog else []
    elif provider=='kite' and exchange=='NSE':
        if owner=='system':raise HTTPException(401,'Sign in and connect Zerodha first')
        from app.kite_workspace import broker
        _,credentials=broker(db,owner)
        rows=live.kite_catalog(owner,credentials)['instruments']
    else:raise HTTPException(422,'Unsupported provider or exchange')
    found=next((r for r in rows if r['symbol']==symbol),None)
    if not found:raise HTTPException(404,'Instrument is not in the current provider catalog')
    return {**found,'instrument_id':identity,'provider':provider}


def current_quote(db,owner,meta):
    if meta['provider']=='binance':
        row=db.scalar(select(Observation).where(Observation.owner=='live_binance',Observation.symbol==meta['symbol']))
        q=dict(row.data) if row else None
        seed=trading.get(db,'public','live_feed','binance_quotes')
        baseline=next((r for r in seed.data['quotes'] if r['symbol']==meta['symbol']),None) if seed else None
        if baseline and (not q or baseline['observed_at']>q['observed_at']):q=baseline
        if not q:raise HTTPException(503,'No provider observation available for this instrument')
        return {**meta,**q,'status':'fresh' if live.age(q['retrieved_at'])<=90 and live.age(q['observed_at'])<=90 else 'stale'}
    from app.kite_workspace import broker,request
    _,c=broker(db,owner)
    key='quote:'+meta['instrument_id']
    cached=trading.get(db,owner,'investing_cache',key)
    if cached and live.age(cached.data['retrieved_at'])<15:return cached.data
    data=request(c,'/quote',{'i':meta['exchange']+':'+meta['symbol']})
    value=data.get(meta['exchange']+':'+meta['symbol'])
    if not value:raise HTTPException(503,'Broker returned no current quote')
    from app.connections import provider_timestamp
    stamp=value.get('last_trade_time')
    observed=provider_timestamp(stamp) if stamp else None
    q={**meta,'price':live.finite(value['last_price']),'currency':'INR','observed_at':observed,'retrieved_at':now(),'source':'Your Zerodha Kite connection','status':'fresh' if observed and live.age(observed)<=90 else 'last_trade','ohlc':value.get('ohlc'),'volume':value.get('volume')}
    trading.put(db,owner,'investing_cache',key,q)
    return q


def provider_candles(db,owner,meta,interval):
    if meta['provider']=='binance':return live.crypto_candles(meta['symbol'],interval)
    from app.kite_workspace import candle_data
    aliases={'1m':'minute','5m':'5minute','15m':'15minute','1h':'60minute','1d':'day'}
    if interval not in aliases:raise HTTPException(422,'Kite supports 1m, 5m, 15m, 1h and 1d intervals here')
    return candle_data(db,owner,meta['symbol'],aliases[interval])


def technical(rows):
    if len(rows)<30:raise HTTPException(422,'At least 30 completed provider candles are required')
    close=pd.Series([r['close'] for r in rows],dtype=float)
    delta=close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean().iloc[-1];loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean().iloc[-1]
    rsi=100-100/(1+gain/loss) if loss>0 else (100 if gain>0 else 50)
    macd=close.ewm(span=12,adjust=False).mean()-close.ewm(span=26,adjust=False).mean()
    sma=close.rolling(20).mean().iloc[-1];std=close.rolling(20).std(ddof=0).iloc[-1]
    return [{'name':'RSI (14 bars)','value':float(rsi),'meaning':'Recent upward versus downward closing-price momentum.'},{'name':'MACD (12/26 bars)','value':float(macd.iloc[-1]),'meaning':'Difference between fast and slow exponential moving averages.'},{'name':'MACD signal (9 bars)','value':float(macd.ewm(span=9,adjust=False).mean().iloc[-1]),'meaning':'Smoothed MACD for comparison with momentum.'},{'name':'Simple average (20 bars)','value':float(sma),'meaning':'Mean of the latest 20 completed closes.'},{'name':'Upper Bollinger band','value':float(sma+2*std),'meaning':'20-bar mean plus two population standard deviations.'},{'name':'Lower Bollinger band','value':float(sma-2*std),'meaning':'20-bar mean minus two population standard deviations.'}]+range_indicators(rows,'meaning')


class Watchlist(BaseModel):
    instrument_ids:list[str]=Field(max_length=100)
class PriceAlert(BaseModel):
    instrument_id:str=Field(max_length=160)
    direction:str=Field(pattern=r'^(above|below)$')
    target:Decimal=Field(gt=0,max_digits=28,decimal_places=12)
    cooldown_seconds:int=Field(default=300,ge=60,le=86400)
class AlertState(BaseModel):
    active:bool
class Compare(BaseModel):
    instrument_ids:list[str]=Field(min_length=2,max_length=4)
    interval:str=Field(default='1d',pattern=r'^(1m|5m|15m|1h|4h|1d|1w)$')


def observe_alert(db,owner,row,quote):
    """Persist monotonic crossings, never evaluate stale or unobserved gaps."""
    a=dict(row.data)
    stamp=quote.get('observed_at')
    if not a['active'] or quote.get('status')!='fresh' or not stamp:return None
    previous_stamp=a.get('last_observed_at')
    if previous_stamp and stamp<=previous_stamp:return None
    previous=a.get('last_price');price=Decimal(str(quote['price']));target=Decimal(a['target'])
    gap=(datetime.fromisoformat(stamp)-datetime.fromisoformat(previous_stamp)).total_seconds() if previous_stamp else None
    crossed=previous is not None and gap is not None and gap<=120 and ((Decimal(previous)<target<=price) if a['direction']=='above' else (Decimal(previous)>target>=price))
    last=datetime.fromisoformat(a['last_fired']) if a.get('last_fired') else None
    event=None
    if crossed and (not last or (datetime.fromisoformat(stamp)-last).total_seconds()>=a['cooldown_seconds']):
        event={'id':trading.ident(),'alert_id':row.key,'instrument_id':a['instrument_id'],'symbol':a['symbol'],'scope':'live','price':str(price),'target':a['target'],'direction':a['direction'],'observed_at':stamp,'source':quote['source'],'currency':a['currency'],'created_at':now()}
        trading.put(db,owner,'event',event['id'],event)
        from app.notifications import enqueue
        enqueue(db,owner,event)
        a['last_fired']=stamp
    a.update(last_price=str(price),last_observed_at=stamp,evaluation_status='rebaselined_after_gap' if gap is not None and gap>120 else 'monitoring',last_error=None)
    row.data=a
    return event


def evaluate_owner(db,owner):
    rows=[r for r in trading.records(db,owner,'live_alert') if r.data['active']]
    quotes={}
    for row in rows:
        identity=row.data['instrument_id']
        try:
            if identity not in quotes:quotes[identity]=current_quote(db,owner,instrument(db,owner,identity))
            quote=quotes[identity]
            if quote['status']!='fresh':row.data={**row.data,'evaluation_status':'waiting_for_fresh_data'}
            else:observe_alert(db,owner,row,quote)
        except HTTPException as error:
            row.data={**row.data,'evaluation_status':'provider_unavailable','last_error':error.detail}


def install(app):
    from app.main import current,database,optional_owner
    dep=Depends(database,scope='function')
    @app.get('/v1/live/instruments')
    def search(request:Request,provider:str=Query(default='binance',pattern=r'^(binance|kite)$'),q:str=Query(default='',max_length=100),currency:str=Query(default='',max_length=20),limit:int=Query(default=100,ge=1,le=500),db=dep):
        owner=optional_owner(request)
        if provider=='binance':
            feed=live.crypto_quotes(q,currency,limit)
            return {**feed,'instruments':[{**r,'instrument_id':identify(provider,r['symbol']),'provider':provider} for r in feed['quotes']]}
        from app.kite_workspace import broker
        _,credentials=broker(db,owner)
        catalog=live.kite_catalog(owner,credentials)
        rows=[r for r in catalog['instruments'] if q.lower() in (r['symbol']+' '+r['name']).lower()]
        return {'instruments':[{**r,'instrument_id':identify(provider,r['symbol'],r['exchange']),'provider':provider} for r in rows[:limit]],'total':len(rows),'source':catalog['source'],'catalog_retrieved_at':catalog['retrieved_at']}
    @app.get('/v1/live/instruments/{identity}/quote')
    def quote(identity:str,request:Request,db=dep):
        owner=optional_owner(request);return current_quote(db,owner,instrument(db,owner,identity))
    @app.get('/v1/live/instruments/{identity}/candles')
    def candles(identity:str,request:Request,interval:str=Query(default='1d',pattern=r'^(1m|5m|15m|1h|4h|1d|1w)$'),db=dep):
        owner=optional_owner(request);meta=instrument(db,owner,identity);return {**provider_candles(db,owner,meta,interval),'instrument_id':identity}
    @app.get('/v1/live/instruments/{identity}/analysis')
    def analysis(identity:str,request:Request,interval:str=Query(default='1d',pattern=r'^(1m|5m|15m|1h|4h|1d|1w)$'),db=dep):
        owner=optional_owner(request);meta=instrument(db,owner,identity);data=provider_candles(db,owner,meta,interval)
        return {'instrument':meta,'interval':interval,'candles':data['candles'],'indicators':technical(data['candles']) if len(data['candles'])>=30 else [],'analysis_note':'Indicators require at least 30 completed candles.','source':data['source'],'observed_through':data['candles'][-1]['date'],'retrieved_at':data['retrieved_at'],'status':data['status'],'fundamentals':None,'fundamentals_status':'No licensed fundamentals provider is configured; price history is not used to invent company ratios.'}
    @app.get('/v1/live/instruments/{identity}/forecast')
    def forecast(identity:str,request:Request,db=dep):
        import json
        owner=optional_owner(request);meta=instrument(db,owner,identity)
        known=next((r for r in market.catalog() if r['symbol']==meta['symbol'] and r['currency']==meta['currency'] and (meta['provider']=='kite' or r.get('provider_ids',{}).get('binance')==meta['symbol'])),None)
        if not known:return {'status':'unavailable','reason':'No evaluated saved model matches this instrument and provider currency.'}
        reports=[]
        for path in sorted((market.ROOT/'models').glob(known['symbol']+'_*_report.json')):
            report=json.loads(path.read_text())
            if report.get('symbol')!=known['symbol'] or report.get('data_sha256')!=known['sha256']:continue
            reports.append(report)
        return {'instrument_id':identity,'status':'saved_research' if reports else 'unavailable','reports':reports,'reason':'Saved measured experiments, not a newly generated forecast at the current quote. Each report retains its original observation date and dataset version.'}
    @app.get('/v1/live/saved')
    def saved(u=Depends(current),db=dep):
        r=trading.get(db,u.id,'investing_watchlist','primary')
        if r:return r.data
        legacy=trading.get(db,u.id,'live_watchlist','primary')
        return {'instrument_ids':[identify('binance',symbol) for symbol in legacy.data['symbols']]} if legacy else {'instrument_ids':[]}
    @app.put('/v1/live/saved')
    def save(req:Watchlist,u=Depends(current),db=dep):
        for identity in req.instrument_ids:instrument(db,u.id,identity)
        data={'instrument_ids':list(dict.fromkeys(req.instrument_ids)),'updated_at':now()};trading.put(db,u.id,'investing_watchlist','primary',data);return data
    @app.get('/v1/live/alerts')
    def alerts(u=Depends(current),db=dep):return [{'id':r.key,**r.data} for r in trading.records(db,u.id,'live_alert')]
    @app.post('/v1/live/alerts')
    def create_alert(req:PriceAlert,u=Depends(current),db=dep):
        meta=instrument(db,u.id,req.instrument_id)
        quote=current_quote(db,u.id,meta)
        key=trading.ident()
        data={**req.model_dump(mode='json'),'symbol':meta['symbol'],'currency':meta['currency'],'active':True,'created_at':now(),'last_price':str(quote['price']) if quote['status']=='fresh' else None,'last_observed_at':quote.get('observed_at') if quote['status']=='fresh' else None,'last_fired':None,'evaluation_status':'monitoring' if quote['status']=='fresh' else 'waiting_for_fresh_data'}
        trading.put(db,u.id,'live_alert',key,data);return {'id':key,**data}
    @app.patch('/v1/live/alerts/{key}')
    def change_alert(key:str,req:AlertState,u=Depends(current),db=dep):
        r=trading.get(db,u.id,'live_alert',key)
        if not r:raise HTTPException(404,'Alert not found')
        r.data={**r.data,'active':req.active,'last_price':None,'last_observed_at':None,'evaluation_status':'waiting_for_fresh_data' if req.active else 'paused'};return {'id':key,**r.data}
    @app.delete('/v1/live/alerts/{key}')
    def remove_alert(key:str,u=Depends(current),db=dep):
        r=trading.get(db,u.id,'live_alert',key)
        if not r:raise HTTPException(404,'Alert not found')
        db.delete(r);return {'deleted':True}
    @app.get('/v1/live/events')
    def events(u=Depends(current),db=dep):return sorted([r.data for r in trading.records(db,u.id,'event') if r.data.get('scope')=='live'],key=lambda r:r['observed_at'],reverse=True)[:100]
    @app.post('/v1/live/comparison')
    def compare(req:Compare,request:Request,db=dep):
        if len(set(req.instrument_ids))!=len(req.instrument_ids):raise HTTPException(422,'Choose distinct instruments')
        owner=optional_owner(request);items=[]
        for identity in req.instrument_ids:
            meta=instrument(db,owner,identity);data=provider_candles(db,owner,meta,req.interval);items.append((meta,data))
        common=sorted(set.intersection(*[{r['date'] for r in data['candles']} for _,data in items]))
        if len(common)<2:raise HTTPException(422,'Not enough common completed timestamps; choose matching trading calendars and intervals')
        series=[]
        for meta,data in items:
            lookup={r['date']:r for r in data['candles']};base=lookup[common[0]]['close']
            series.append({'instrument':meta,'source':data['source'],'status':data['status'],'retrieved_at':data['retrieved_at'],'points':[{'date':date,'value':lookup[date]['close']/base*100} for date in common]})
        return {'series':series,'start':common[0],'end':common[-1],'observations':len(common),'note':'Starts at 100 on a shared completed observation. Native-currency returns; not FX-adjusted. No missing timestamps are filled.'}
