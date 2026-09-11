"""OAuth resource-server configuration for a deployed MCP endpoint.

The operator supplies an existing OAuth issuer; Studio never invents an identity provider
or exposes a public unauthenticated production endpoint.
"""
import os
from urllib.parse import urlsplit
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings


class JWTVerifier(TokenVerifier):
    def __init__(self, issuer, audience, jwks_url):
        import jwt
        self.issuer, self.audience = issuer, audience
        self.keys = jwt.PyJWKClient(jwks_url, cache_keys=True)

    async def verify_token(self, token):
        import asyncio
        import jwt
        def verify():
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=['RS256', 'ES256'],
                                audience=self.audience, issuer=self.issuer,
                                options={'require': ['exp', 'iss', 'aud', 'sub']})
            scopes = claims.get('scope', '')
            if not isinstance(scopes, str):
                return None
            return AccessToken(token=token, client_id=str(claims['sub']), scopes=scopes.split(),
                               expires_at=int(claims['exp']), resource=self.audience)
        try:
            return await asyncio.to_thread(verify)
        except Exception:
            return None


def oauth_settings():
    values = {key: os.environ.get(key, '') for key in (
        'STUDIO_MCP_ISSUER', 'STUDIO_MCP_RESOURCE', 'STUDIO_MCP_JWKS')}
    for key, value in values.items():
        p = urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment:
            raise ValueError(f'{key} must be an explicitly configured HTTPS URL before enabling remote MCP.')
    issuer, resource, jwks = values.values()
    host = urlsplit(resource).netloc
    return {'token_verifier': JWTVerifier(issuer, resource, jwks),
            'auth': AuthSettings(issuer_url=issuer, resource_server_url=resource, required_scopes=['studio:operate'], validate_token_resource=True),
            'transport_security': TransportSecuritySettings(enable_dns_rebinding_protection=True,
                allowed_hosts=[host, '127.0.0.1:*', 'localhost:*'],
                allowed_origins=[f'https://{host}'])}
