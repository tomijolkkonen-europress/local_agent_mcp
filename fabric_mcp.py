"""Lokaali MCP-client Fabricin data agentin MCP-serverille (streamable HTTP)."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

import httpx2
from azure.core.credentials import TokenCredential
from azure.identity import (
    AzureCliCredential,
    ChainedTokenCredential,
    InteractiveBrowserCredential,
)
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from config import FABRIC_SCOPE, Settings


def build_credential(tenant_id: str | None) -> TokenCredential:
    # Ensin `az login` -kirjautuminen; jos sitä ei ole, avataan selainkirjautuminen.
    return ChainedTokenCredential(
        AzureCliCredential(tenant_id=tenant_id),
        InteractiveBrowserCredential(tenant_id=tenant_id),
    )


class FabricTokenAuth(httpx2.Auth):
    """Liittää jokaiseen pyyntöön tuoreen Fabric-bearer-tokenin.

    Token haetaan pyyntökohtaisesti (azure-identity välimuistittaa sen), jotta
    yli tunnin kestävä sessio ei kaadu vanhentuneeseen tokeniin.
    """

    def __init__(self, credential: TokenCredential):
        self._credential = credential

    def _token(self) -> str:
        return self._credential.get_token(FABRIC_SCOPE).token

    def auth_flow(self, request: httpx2.Request) -> Generator[httpx2.Request, httpx2.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token()}"
        yield request

    async def async_auth_flow(self, request: httpx2.Request) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        # get_token on synkroninen ja voi avata selaimen -> ei blokata event looppia.
        token = await asyncio.to_thread(self._token)
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


@asynccontextmanager
async def connect(settings: Settings) -> AsyncGenerator[ClientSession, None]:
    """Avaa MCP-session Fabricin data agentiin ja tekee initialize-kättelyn."""
    credential = build_credential(settings.tenant_id)
    # Haetaan token kerran etukäteen, jotta mahdollinen selainkirjautuminen
    # tapahtuu ennen yhteyden avausta eikä kesken MCP-kättelyn.
    await asyncio.to_thread(credential.get_token, FABRIC_SCOPE)

    http_client = create_mcp_http_client(
        timeout=httpx2.Timeout(30.0, read=settings.mcp_read_timeout_s),
        auth=FabricTokenAuth(credential),
    )
    async with http_client:
        async with streamable_http_client(settings.fabric_mcp_url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
