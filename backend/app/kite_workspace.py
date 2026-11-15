"""Hosted multi-user Kite connection: application credentials stay on the server."""
import os
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import httpx
from fastapi import Depends,HTTPException,Query
from app import trading,connections
from app.store import now
from app.live import kite_catalog,age,finite

IST=ZoneInfo('Asia/Kolkata')

def setup():
    configured=bool(os.getenv('KITE_API_KEY') and os.getenv('KITE_API_SECRET'))
    approved=os.getenv('KITE_MULTI_USER_ENABLED','false').lower()=='true'
    return {'provider':'Zerodha Kite','configured':configured,'multi_user_enabled':approved,'available':configured and approved,'callback':os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/')+'/v1/connections/kite/callback','message':'Connect your Zerodha account through its official login.' if configured and approved else 'Zerodha connections are awaiting site-operator configuration and multi-user access approval. Public crypto markets remain available.','real_money_orders_enabled':False}

def broker(db,owner):
    r=trading.get(db,owner,'connection','kite')
    if not r:raise HTTPException(409,'Connect your Zerodha account first')
    c=connections.credentials(r.data)
    if not c.get('api_key') or not c.get('access_token'):raise HTTPException(409,'Complete Zerodha login to activate this connection')
    return r,c

def request(c,path,params=None):
    try:
        response=httpx.get('https://api.kite.trade'+path,headers={'X-Kite-Version':'3','Authorization':f"token {c['api_key']}:{c['access_token']}"},params=params,timeout=20)
        if response.status_code==403:
            raise HTTPException(409,'Zerodha denied access. Reconnect if the session expired; otherwise the site operator must check this application’s data entitlement.')
        if response.status_code==429:raise HTTPException(429,'Zerodha request limit reached. Wait briefly before refreshing.')
        response.raise_for_status()
        return response.json()['data']
    except (httpx.HTTPError,KeyError,ValueError):raise HTTPException(502,'Zerodha is unavailable or returned an invalid response. No sample data was substituted.')

def install(app):
    from app.main import current,database
    dep=Depends(database,scope='function')
    @app.get('/v1/kite/setup')
    def config():return setup()
    @app.get('/v1/kite/status')
    def status(u=Depends(current),db=dep):
        r=trading.get(db,u.id,'connection','kite')
        return {**setup(),'connection':connections.public(r.data) if r else None}
    @app.post('/v1/kite/connect')
    def connect(u=Depends(current),db=dep):
        config=setup()
        if not config['available']:raise HTTPException(503,config['message'])
        r=trading.get(db,u.id,'connection','kite')
        if not r or r.data.get('credential_mode')!='hosted':
            trading.put(db,u.id,'connection','kite',{'provider':'kite','credential_mode':'hosted','secret':connections.seal({}),'status':'awaiting_authorization','connected_at':now(),'last_sync':None,'error':None})
        return connections.authorize(db,u.id,'kite')
    @app.post('/v1/kite/verify')
    def verify(u=Depends(current),db=dep):
        r,c=broker(db,u.id)
        try:
            profile=request(c,'/user/profile')
            r.data={**r.data,'status':'verified','verified_at':now(),'account':{'broker_user_id':profile.get('user_id'),'name':profile.get('user_name'),'exchanges':profile.get('exchanges',[])},'error':None}
        except HTTPException as e:
            r.data={**r.data,'status':'reconnect_required' if e.status_code==409 else 'unavailable','last_attempt':now(),'error':e.detail}
        return connections.public(r.data)
    @app.post('/v1/kite/portfolio/refresh')
    def portfolio(u=Depends(current),db=dep):
        r,c=broker(db,u.id)
        # Both provider reads must succeed before publishing this account snapshot.
        holdings=request(c,'/portfolio/holdings')
        positions=request(c,'/portfolio/positions')
        received=now()
        snapshot={'holdings':holdings,'positions':positions,'retrieved_at':received,'source':'Your Zerodha Kite account','note':'Broker-reported snapshot. Retrieval time is not an individual price observation timestamp. P&L is supplied by the broker; no virtual balances are included.'}
        trading.put(db,u.id,'kite_portfolio','current',snapshot)
        r.data={**r.data,'last_portfolio_sync':received,'error':None}
        return snapshot
    @app.get('/v1/kite/portfolio')
    def saved_portfolio(u=Depends(current),db=dep):
        r=trading.get(db,u.id,'kite_portfolio','current')
        return {**r.data,'status':'stale' if age(r.data['retrieved_at'])>90 else 'recent_snapshot'} if r else {'holdings':[],'positions':{'net':[],'day':[]},'status':'unavailable','note':'Refresh to retrieve actual holdings and positions from your account.'}
    @app.get('/v1/kite/{symbol}/candles')
    def candles(symbol:str,interval:str=Query(default='day',pattern=r'^(minute|3minute|5minute|15minute|30minute|60minute|day)$'),u=Depends(current),db=dep):
        return candle_data(db,u.id,symbol,interval)


def candle_data(db,owner,symbol,interval):
    _,c=broker(db,owner)
    catalog=kite_catalog(owner,c)
    instrument=next((r for r in catalog['instruments'] if r['symbol']==symbol),None)
    if not instrument:raise HTTPException(404,'Instrument is not in your broker catalog')
    key=symbol+':'+interval
    saved=trading.get(db,owner,'kite_candles',key)
    if saved and age(saved.data['retrieved_at'])<30:return saved.data
    end=datetime.now(IST);start=end-timedelta(days=365 if interval=='day' else 7)
    data=request(c,'/instruments/historical/'+str(instrument['instrument_token'])+'/'+interval,{'from':start.strftime('%Y-%m-%d %H:%M:%S'),'to':end.strftime('%Y-%m-%d %H:%M:%S'),'continuous':0,'oi':0})
    minutes={'minute':1,'3minute':3,'5minute':5,'15minute':15,'30minute':30,'60minute':60}
    rows=[]
    for row in data['candles']:
        stamp=datetime.fromisoformat(row[0]);stamp=stamp.replace(tzinfo=IST) if stamp.tzinfo is None else stamp
        # Daily candle completes at session close; intraday completes at interval end.
        completed=stamp.replace(hour=15,minute=30,second=0) if interval=='day' else stamp+timedelta(minutes=minutes[interval])
        if completed>end:continue
        rows.append({'date':stamp.astimezone(timezone.utc).isoformat(),'open':finite(row[1]),'high':finite(row[2]),'low':finite(row[3]),'close':finite(row[4]),'volume':finite(row[5])})
    result={'symbol':symbol,'interval':interval,'candles':rows[-300:],'source':'Your Zerodha historical-data entitlement','retrieved_at':now(),'status':'provider_response','note':'Completed NSE regular-session candles only. The currently forming candle is excluded. Special-session completion times are not supported.'}
    trading.put(db,owner,'kite_candles',key,result)
    return result
