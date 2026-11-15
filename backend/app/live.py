"""Provider-discovered current markets. Never falls back to capstone history."""
import csv
import io
import math
from datetime import datetime, timezone
import httpx
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app import trading
from app.store import DB, now

BINANCE = 'https://data-api.binance.vision'

def age(stamp):
    return max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds())

def finite(value):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('Non-finite provider value')
    return n

def read_record(owner, key):
    with DB() as db:
        r=trading.get(db,owner,'live_feed',key)
        return dict(r.data) if r else None

def write_record(owner,key,data):
    with DB.begin() as db:
        trading.put(db,owner,'live_feed',key,data)

def refresh_crypto():
    catalog=read_record('public','binance_catalog')
    with httpx.Client(timeout=25) as client:
        if not catalog or age(catalog['retrieved_at'])>=86400:
            response=client.get(BINANCE+'/api/v3/exchangeInfo')
            response.raise_for_status()
            instruments=[{'symbol':r['symbol'],'name':r['baseAsset']+'/'+r['quoteAsset'],'base_asset':r['baseAsset'],'currency':r['quoteAsset'],'exchange':'Binance','segment':'crypto'} for r in response.json()['symbols'] if r['status']=='TRADING' and r.get('isSpotTradingAllowed',False)]
            if not instruments:
                raise ValueError('Provider returned an empty trading universe')
            catalog={'instruments':instruments,'retrieved_at':now(),'source':'Binance exchangeInfo'}
            write_record('public','binance_catalog',catalog)
        response=client.get(BINANCE+'/api/v3/ticker/24hr')
        response.raise_for_status()
        known={r['symbol']:r for r in catalog['instruments']}
        received=now()
        quotes=[]
        for r in response.json():
            if r['symbol'] not in known:
                continue
            price=finite(r['lastPrice'])
            if price<=0:
                continue
            quotes.append({**known[r['symbol']],'price':price,'change_pct':finite(r['priceChangePercent']),'high':finite(r['highPrice']),'low':finite(r['lowPrice']),'base_volume':finite(r['volume']),'quote_volume':finite(r['quoteVolume']),'observed_at':datetime.fromtimestamp(int(r['closeTime'])/1000,timezone.utc).isoformat(),'window_start':datetime.fromtimestamp(int(r['openTime'])/1000,timezone.utc).isoformat(),'retrieved_at':received,'source':'Binance public 24-hour ticker','source_url':BINANCE+'/api/v3/ticker/24hr'})
        if not quotes:
            raise ValueError('Provider returned no valid quotes')
        write_record('public','binance_quotes',{'quotes':quotes,'retrieved_at':received,'catalog_retrieved_at':catalog['retrieved_at'],'error':None})
    return {'status':'updated','instruments':len(catalog['instruments']),'quotes':len(quotes),'retrieved_at':received}

def crypto_quotes(query='',currency='',limit=100):
    feed=read_record('public','binance_quotes')
    from app.store import Observation
    from sqlalchemy import select
    with DB() as db:
        streamed=[r.data for r in db.scalars(select(Observation).where(Observation.owner=='live_binance'))]
    stream=read_record('public','binance_stream')
    if not feed and not streamed:
        return {'status':'unavailable','quotes':[],'total':0,'error':'Waiting for a successful provider refresh. Historical prices are not substituted.'}
    if not feed:
        catalog=read_record('public','binance_catalog')
        feed={'quotes':[],'retrieved_at':stream['retrieved_at'] if stream else now(),'catalog_retrieved_at':catalog['retrieved_at'] if catalog else None}
    merged={r['symbol']:r for r in feed['quotes']}
    for r in streamed:
        if r['symbol'] not in merged or r['observed_at']>merged[r['symbol']]['observed_at']:merged[r['symbol']]=r
    catalog=read_record('public','binance_catalog')
    active={r['symbol'] for r in catalog['instruments']} if catalog else set(merged)
    feed={**feed,'quotes':[r for symbol,r in merged.items() if symbol in active]}
    if stream and stream['retrieved_at']>feed['retrieved_at']:feed['retrieved_at']=stream['retrieved_at']
    rows=[r for r in feed['quotes'] if query.lower() in (r['symbol']+' '+r['name']).lower() and (not currency or r['currency']==currency)]
    rows.sort(key=lambda r:r['quote_volume'],reverse=True)
    stale=age(feed['retrieved_at'])>90
    return {'status':'stale' if stale else 'fresh','retrieved_at':feed['retrieved_at'],'catalog_retrieved_at':feed['catalog_retrieved_at'],'refresh_seconds':5,'total':len(rows),'currency_counts':{c:sum(r['currency']==c for r in feed['quotes']) for c in {r['currency'] for r in feed['quotes']}},'currencies':sorted({r['currency'] for r in feed['quotes']}),'quotes':[{**r,'status':'stale' if stale or age(r['observed_at'])>90 else 'fresh'} for r in rows[:limit]],'note':'Current public spot-market observations. 24-hour change is a rolling window. Quote-volume rankings are comparable only within the same quote currency. No real-money order execution.'}

def crypto_candles(symbol,interval):
    catalog=read_record('public','binance_catalog')
    if not catalog or symbol not in {r['symbol'] for r in catalog['instruments']}:
        raise HTTPException(404,'Instrument is not in the current provider catalog')
    key='candles:'+symbol+':'+interval
    cached=read_record('public',key)
    if cached and age(cached['retrieved_at'])<30:
        return cached
    try:
        response=httpx.get(BINANCE+'/api/v3/klines',params={'symbol':symbol,'interval':interval,'limit':300},timeout=15)
        response.raise_for_status()
        current_ms=datetime.now(timezone.utc).timestamp()*1000
        rows=[{'date':datetime.fromtimestamp(r[0]/1000,timezone.utc).isoformat(),'open':finite(r[1]),'high':finite(r[2]),'low':finite(r[3]),'close':finite(r[4]),'volume':finite(r[5])} for r in response.json() if r[6]<current_ms]
        if not rows:raise ValueError('No completed candles')
        result={'symbol':symbol,'interval':interval,'candles':rows,'retrieved_at':now(),'observed_through':rows[-1]['date'],'source':'Binance public klines','status':'fresh','note':'Completed candles only. The currently forming candle is excluded.'}
        write_record('public',key,result)
        return result
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        if cached:return {**cached,'status':'stale','error':'Provider refresh failed. Showing the previous successful response with its original timestamp.'}
        raise HTTPException(503,'Live chart provider is unavailable. No recorded capstone dataset was substituted.')

def kite_catalog(owner,credentials):
    cached=read_record(owner,'kite_catalog')
    if cached and age(cached['retrieved_at'])<86400:return cached
    headers={'X-Kite-Version':'3','Authorization':f"token {credentials['api_key']}:{credentials['access_token']}"}
    response=httpx.get('https://api.kite.trade/instruments/NSE',headers=headers,timeout=30)
    response.raise_for_status()
    rows=[{'symbol':r['tradingsymbol'],'name':r['name'] or r['tradingsymbol'],'exchange':r['exchange'],'instrument_token':r['instrument_token'],'currency':'INR','segment':r['segment'],'lot_size':int(r['lot_size'])} for r in csv.DictReader(io.StringIO(response.text)) if r['instrument_type']=='EQ' or r['segment']=='INDICES']
    if not rows:raise ValueError('Empty broker instrument catalog')
    result={'instruments':rows,'retrieved_at':now(),'source':'Your Kite instrument catalog'}
    write_record(owner,'kite_catalog',result)
    return result

class LiveWatch(BaseModel):
    symbols:list[str]=Field(max_length=100)

def install(app):
    from app.main import current,database
    dep=Depends(database,scope='function')
    @app.get('/v1/live/crypto')
    def crypto(q:str=Query(default='',max_length=100),currency:str=Query(default='',max_length=20),limit:int=Query(default=100,ge=1,le=500)):
        return crypto_quotes(q,currency,limit)
    @app.get('/v1/live/crypto/{symbol}/candles')
    def candles(symbol:str,interval:str=Query(default='1h',pattern=r'^(1m|5m|15m|1h|4h|1d|1w)$')):
        return crypto_candles(symbol,interval)
    @app.get('/v1/live/watchlist')
    def watchlist(u=Depends(current),db=dep):
        r=trading.get(db,u.id,'live_watchlist','primary')
        return r.data if r else {'symbols':[]}
    @app.put('/v1/live/watchlist')
    def save_watchlist(req:LiveWatch,u=Depends(current),db=dep):
        catalog=trading.get(db,'public','live_feed','binance_catalog')
        valid={r['symbol'] for r in catalog.data['instruments']} if catalog else set()
        if any(s not in valid for s in req.symbols):raise HTTPException(422,'Choose instruments from the current provider catalog')
        data={'symbols':list(dict.fromkeys(req.symbols)),'updated_at':now()}
        trading.put(db,u.id,'live_watchlist','primary',data)
        return data
    @app.get('/v1/live/india/search')
    def india(q:str=Query(default='',max_length=100),u=Depends(current),db=dep):
        from app.connections import credentials
        r=trading.get(db,u.id,'connection','kite')
        if not r:raise HTTPException(409,'Connect your Zerodha Kite account to search the broker instrument catalog and retrieve Indian-market quotes.')
        try:
            catalog=kite_catalog(u.id,credentials(r.data))
            rows=[r for r in catalog['instruments'] if q.lower() in (r['symbol']+' '+r['name']).lower()]
            return {'instruments':rows[:100],'total':len(rows),'source':catalog['source'],'catalog_retrieved_at':catalog['retrieved_at']}
        except (httpx.HTTPError,KeyError,ValueError):raise HTTPException(502,'Broker instrument discovery failed. Check your token and market-data entitlement.')
    @app.get('/v1/live/india/{symbol}/quote')
    def india_quote(symbol:str,u=Depends(current),db=dep):
        from app.connections import credentials,provider_timestamp
        r=trading.get(db,u.id,'connection','kite')
        if not r:raise HTTPException(409,'Connect your Kite account first')
        try:
            c=credentials(r.data);catalog=kite_catalog(u.id,c)
            instrument=next((r for r in catalog['instruments'] if r['symbol']==symbol),None)
            if not instrument:raise HTTPException(404,'Instrument is not in your broker catalog')
            headers={'X-Kite-Version':'3','Authorization':f"token {c['api_key']}:{c['access_token']}"}
            response=httpx.get('https://api.kite.trade/quote',params={'i':instrument['exchange']+':'+symbol},headers=headers,timeout=15)
            response.raise_for_status();item=response.json()['data'].get(instrument['exchange']+':'+symbol)
            if not item:raise HTTPException(404,'Broker returned no quote for this instrument')
            stamp=item.get('last_trade_time');retrieved=now()
            return {**instrument,'price':finite(item['last_price']),'ohlc':item.get('ohlc'),'volume':item.get('volume'),'depth':item.get('depth'),'observed_at':provider_timestamp(stamp) if stamp else None,'retrieved_at':retrieved,'status':'fresh' if stamp and age(provider_timestamp(stamp))<=90 else 'last_trade','source':'Your Zerodha Kite connection','note':'Last-trade time is distinct from retrieval time. A quote outside trading hours is not a fresh executable price.'}
        except (httpx.HTTPError,KeyError,ValueError):raise HTTPException(502,'Broker quote failed. Check token expiry and market-data entitlement.')
    @app.get('/v1/live/holdings')
    def holdings(u=Depends(current),db=dep):
        return {'accounts':[{'provider':r.key,**r.data} for r in trading.records(db,u.id,'broker_holdings')],'connections':[{'provider':r.key,'status':r.data.get('status'),'last_sync':r.data.get('last_sync'),'error':r.data.get('error')} for r in trading.records(db,u.id,'connection')],'note':'Broker-reported holdings are separate from virtual portfolios and reconstructed trade history. Missing cost or price remains unavailable.'}


def stream_forever():
    """One shared provider connection; persist only changed symbol snapshots."""
    import json
    import logging
    import time
    from websockets.sync.client import connect
    from app.market import persist_quotes
    log=logging.getLogger('eye.live')
    delay=5
    while True:
        try:
            catalog=read_record('public','binance_catalog')
            if not catalog or age(catalog['retrieved_at'])>=86400:
                refresh_crypto()
                catalog=read_record('public','binance_catalog')
            known={r['symbol']:r for r in catalog['instruments']}
            pending={}
            last_flush=time.monotonic()
            with connect('wss://data-stream.binance.vision/ws/!miniTicker@arr',open_timeout=15,close_timeout=3,max_size=4_000_000) as socket:
                delay=5
                while True:
                    events=json.loads(socket.recv(timeout=30))
                    received=now()
                    for item in events:
                        symbol=item['s']
                        if symbol not in known:continue
                        price=finite(item['c']);opening=finite(item['o'])
                        if price<=0 or opening<=0:continue
                        pending[symbol]={**known[symbol],'price':price,'change_pct':(price/opening-1)*100,'high':finite(item['h']),'low':finite(item['l']),'base_volume':finite(item['v']),'quote_volume':finite(item['q']),'observed_at':datetime.fromtimestamp(item['E']/1000,timezone.utc).isoformat(),'retrieved_at':received,'source':'Binance public mini-ticker stream','source_url':'wss://data-stream.binance.vision/ws/!miniTicker@arr'}
                    if pending and time.monotonic()-last_flush>=5:
                        persist_quotes('live_binance',pending)
                        write_record('public','binance_stream',{'retrieved_at':received,'status':'connected','last_error':None})
                        pending.clear();last_flush=time.monotonic()
        except Exception:
            log.exception('Live provider stream interrupted; timestamps expire without synthetic fallback')
            write_record('public','binance_stream_error',{'retrieved_at':now(),'error':'Provider stream interrupted. Reconnecting; previous prices retain their original timestamps.'})
            try:
                snapshot=read_record('public','binance_quotes')
                if not snapshot or age(snapshot['retrieved_at'])>90:refresh_crypto()
            except Exception:
                log.warning('REST recovery unavailable; retaining explicitly stale observations')
            time.sleep(delay)
            delay=min(delay*2,60)
