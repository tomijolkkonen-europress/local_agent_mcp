# local_agent_mcp

Lokaali data-agentti, joka käyttää Microsoft Fabricin data agentia MCP:n kautta.

```
käyttäjä ──> agent.py (Claude, päättely) ──> fabric_mcp.py (MCP-client) ──HTTP──> Fabric data agent (MCP-serveri)
```

- `agent.py` – Claude-agentti (Anthropic SDK:n tool runner). Fabricin data agentin MCP-työkalu annetaan Claudelle työkaluksi.
- `fabric_mcp.py` – MCP-client (streamable HTTP). Hakee Fabric-tokenin `azure-identity`:llä (`az login` tai selainkirjautuminen) ja liittää sen jokaiseen pyyntöön.
- `config.py` – asetukset `.env`- ja `mcp.json`-tiedostoista.

## Asennus

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # aseta ANTHROPIC_API_KEY
```

Lataa data agentin `mcp.json` Fabricista (data agent → Settings → Model Context Protocol) ja tallenna se repon juureen nimellä `mcp.json` (mallina `mcp.example.json`). Tiedosto on .gitignoressa.

Data agentin pitää olla **julkaistu**, ja tunnuksellasi pitää olla pääsy workspaceen ja agenttiin.

## Käyttö

```powershell
.\.venv\Scripts\python agent.py --list-tools   # testaa MCP-yhteys
.\.venv\Scripts\python agent.py "Mitä dataa sinulla on?"
.\.venv\Scripts\python agent.py                # interaktiivinen keskustelu
```

Ensimmäisellä kerralla avautuu selainkirjautuminen (jos Azure CLI:n `az login` ei ole käytössä).

## Huomio tietoturvasta

Data agentin vastaukset (eli Fabricin dataa) lähetetään Anthropicin API:in Clauden käsiteltäväksi, eli Fabricin compliance-rajan ulkopuolelle. Varmista ennen käyttöä, että tämä on sallittua datan luokituksen ja yrityksen tietoturvaohjeiden mukaan.
