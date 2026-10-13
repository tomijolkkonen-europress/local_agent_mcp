import unittest
from types import SimpleNamespace

import httpx2

from fabric_mcp import FABRIC_SCOPE, FabricTokenAuth


class StaticCredential:
    def get_token(self, *scopes):
        if scopes != (FABRIC_SCOPE,):
            raise AssertionError(f"Unexpected token scope: {scopes}")
        return SimpleNamespace(token="test-token")


class FabricTokenAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth = FabricTokenAuth(StaticCredential())

    def test_sync_auth_flow_adds_bearer_token(self):
        request = httpx2.Request("GET", "https://example.com")
        flow = self.auth.auth_flow(request)

        next(flow)

        self.assertEqual(request.headers["Authorization"], "Bearer test-token")
        flow.close()

    async def test_async_auth_flow_adds_bearer_token(self):
        request = httpx2.Request("GET", "https://example.com")
        flow = self.auth.async_auth_flow(request)

        sent_request = await anext(flow)

        self.assertEqual(sent_request.headers["Authorization"], "Bearer test-token")
        await flow.aclose()


if __name__ == "__main__":
    unittest.main()
