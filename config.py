"""Asetukset luetaan ympäristömuuttujista / .env-tiedostosta."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Puuttuva asetus: {name} (katso .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    fabric_mcp_url: str
    tenant_id: str | None
    model: str
    effort: str
    max_tokens: int
    mcp_read_timeout_s: float


def _url_from_mcp_json(path: Path, server_name: str | None) -> str | None:
    """Lukee URL:n Fabricista ladatusta mcp.json-tiedostosta (VS Code -muoto)."""
    if not path.is_file():
        return None
    servers = json.loads(path.read_text(encoding="utf-8")).get("servers", {})
    if not servers:
        raise SystemExit(f"{path}: ei palvelimia 'servers'-avaimen alla")
    if server_name:
        if server_name not in servers:
            raise SystemExit(f"{path}: palvelinta '{server_name}' ei löydy ({', '.join(servers)})")
        return servers[server_name]["url"]
    if len(servers) > 1:
        raise SystemExit(f"{path}: useita palvelimia, valitse FABRIC_MCP_SERVER-asetuksella ({', '.join(servers)})")
    return next(iter(servers.values()))["url"]


def load_settings() -> Settings:
    # MCP-URL haetaan järjestyksessä: FABRIC_MCP_URL, mcp.json (Fabricin data
    # agentin Settings -> Model Context Protocol -välilehdeltä ladattu tiedosto),
    # tai koottuna workspace- ja data agent -ID:istä.
    mcp_json = Path(os.getenv("MCP_CONFIG_FILE", Path(__file__).with_name("mcp.json")))
    url = os.getenv("FABRIC_MCP_URL", "").strip() or _url_from_mcp_json(
        mcp_json, os.getenv("FABRIC_MCP_SERVER") or None
    )
    if not url:
        workspace_id = _required("FABRIC_WORKSPACE_ID")
        data_agent_id = _required("FABRIC_DATA_AGENT_ID")
        url = (
            f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspace_id}"
            f"/dataagents/{data_agent_id}/agent"
        )

    return Settings(
        fabric_mcp_url=url,
        tenant_id=os.getenv("AZURE_TENANT_ID") or None,
        model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        effort=os.getenv("CLAUDE_EFFORT", "medium"),
        max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "16000")),
        # Data agent voi ajaa useita kyselyitä yhteen kysymykseen, joten
        # lukutimeout on reilu.
        mcp_read_timeout_s=float(os.getenv("MCP_READ_TIMEOUT_S", "600")),
    )
