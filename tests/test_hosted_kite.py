"""Controlled hosted-app auth checks; these do not verify a real broker account."""
from urllib.parse import urlparse,parse_qs
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import connections,store
from app.store import Record


def test_hosted_kite_requires_operator_configuration(alice,monkeypatch):
    monkeypatch.delenv('KITE_API_KEY',raising=False)
    monkeypatch.delenv('KITE_API_SECRET',raising=False)
    assert not alice.get('/v1/kite/setup').json()['available']
    assert alice.post('/v1/kite/connect').status_code==503


def test_hosted_kite_token_is_private_and_application_secret_is_not_copied(alice,monkeypatch):
    monkeypatch.setenv('KITE_API_KEY','controlled-public-app-key')
    monkeypatch.setenv('KITE_API_SECRET','controlled-server-secret')
    monkeypatch.setenv('KITE_MULTI_USER_ENABLED','true')
    login=alice.post('/v1/kite/connect').json()
    params=parse_qs(urlparse(login['url']).query)
    state=parse_qs(params['redirect_params'][0])['state'][0]
    assert 'controlled-server-secret' not in str(login)
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'data':{'access_token':'controlled-user-token'}}
    class Provider:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Response()
    with patch.object(connections.httpx,'Client',Provider):
        response=alice.get('/v1/connections/kite/callback',params={'state':state,'request_token':'controlled-request-token'},follow_redirects=False)
    assert response.status_code==303
    assert alice.get('/v1/connections/kite/callback',params={'state':state,'request_token':'replay'},follow_redirects=False).status_code==422
    with store.DB() as db:
        r=db.query(Record).filter_by(kind='connection',key='kite').one()
        assert connections.unseal(r.data['secret'])=={'access_token':'controlled-user-token'}
    assert 'controlled-user-token' not in alice.get('/v1/kite/status').text
    with TestClient(app,headers={'X-Eye-Client':'workspace'}) as other:
        other.post('/v1/auth/register',json={'name':'Other investor','email':'other-kite@example.com','password':'long-password-123'})
        assert other.get('/v1/kite/status').json()['connection'] is None
        assert other.get('/v1/kite/portfolio').json()['status']=='unavailable'
