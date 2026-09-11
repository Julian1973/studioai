"""Run with requirements-mcp.txt installed. All protocol tests use fake production APIs."""
import asyncio
import json
import pytest
pytest.importorskip("mcp", reason="Run optional MCP tests in .venv-mcp with requirements-mcp.txt")
from studio_agent_gateway import Gateway
from studio_mcp import build


class API:
    base='http://127.0.0.1:8899'
    def __init__(self): self.calls=[]
    def request(self, method, path, data=None):
        self.calls.append((method,path,data))
        if path=='/api/projects':return {'projects':[{'id':'example'}]}
        return {'ok':True,'jobId':'job-123'}


def test_mcp_tools_and_resource_use_same_gateway(tmp_path):
    api=API();server=build(Gateway(api,tmp_path))
    async def run():
        tools=await server.list_tools()
        assert {t.name for t in tools}=={'studio_read','studio_command','studio_receipt'}
        assert next(t for t in tools if t.name=='studio_command').annotations.idempotentHint
        result=await server.call_tool('studio_read',{'view':'projects'})
        assert 'example' in str(result)
        args={'operation':'project_command','arguments':{'projectId':'example','episode':'1','action':'continue','expectedRevision':0},'command_id':'command-123'}
        await server.call_tool('studio_command',args)
        await server.call_tool('studio_command',args)
        assert len([c for c in api.calls if c[0]=='POST'])==1
        assert 'StudioAI' in str(await server.read_resource('studio://workflow'))
    asyncio.run(run())


def test_remote_transport_requires_explicit_configuration(monkeypatch):
    from studio_mcp_auth import oauth_settings
    for key in ('STUDIO_MCP_ISSUER','STUDIO_MCP_RESOURCE','STUDIO_MCP_JWKS'):monkeypatch.delenv(key,raising=False)
    with pytest.raises(ValueError,match='HTTPS'):oauth_settings()


def test_oauth_verifies_signature_audience_expiry_and_scope():
    from studio_mcp_auth import JWTVerifier
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt,time
    from types import SimpleNamespace
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    verifier=JWTVerifier('https://issuer.example','https://studio.example/mcp','https://issuer.example/jwks')
    verifier.keys=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key()))
    claims={'iss':'https://issuer.example','aud':'https://studio.example/mcp','sub':'operator',
            'scope':'studio:operate','exp':int(time.time())+60}
    async def run():
        value=await verifier.verify_token(jwt.encode(claims,key,algorithm='RS256'))
        assert value.scopes==['studio:operate']
        for changed in ({'aud':'https://other.example'},{'exp':1},{'iss':'https://wrong.example'}):
            assert await verifier.verify_token(jwt.encode({**claims,**changed},key,algorithm='RS256')) is None
        assert await verifier.verify_token('invalid') is None
    asyncio.run(run())


def test_http_middleware_rejects_anonymous_and_wrong_scope(tmp_path):
    from starlette.testclient import TestClient
    from mcp.server.auth.provider import AccessToken, TokenVerifier
    from mcp.server.auth.settings import AuthSettings
    class Tokens(TokenVerifier):
        async def verify_token(self, token):
            if token not in {'allowed','wrong-scope'}:return None
            return AccessToken(token=token,client_id='test',scopes=['studio:operate'] if token=='allowed' else [], resource='https://studio.example/mcp')
    server=build(Gateway(API(),tmp_path),stateless_http=True,token_verifier=Tokens(),
        auth=AuthSettings(issuer_url='https://issuer.example',resource_server_url='https://studio.example/mcp',required_scopes=['studio:operate'], validate_token_resource=True))
    with TestClient(server.streamable_http_app(),base_url='http://127.0.0.1:8000') as client:
        request={'jsonrpc':'2.0','id':1,'method':'initialize','params':{
          'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}}
        headers={'Accept':'application/json, text/event-stream'}
        assert client.post('/mcp',json=request,headers=headers).status_code==401
        assert client.post('/mcp',json=request,headers={**headers,'Authorization':'Bearer wrong-scope'}).status_code==403
        assert client.post('/mcp',json=request,headers={**headers,'Authorization':'Bearer allowed'}).status_code==200
