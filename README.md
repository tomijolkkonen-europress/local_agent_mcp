# PRIME-data-agentti (local_agent_mcp)

Lokaalisti ajettava, Pythonilla tehty data-agentti **PRIME ERP -projektin Azure DevOps -sisällön tutkimiseen**.

Agentti on MCP-yhteydessä Microsoft Fabricin data agentiin (**PRIME_Knowledge_DataAgent**), joka toimii MCP-serverinä. Fabricin data agentti hakee tiedot Fabric Lakehousesta, jonne PRIME:n DevOps-data on tuotu ja jalostettu. Paikallinen agentti on MCP-client. Kielimallina se käyttää **GitHub Copilotia**, joka päättää, mitä Fabricilta kysytään, ja kokoaa vastaukset.

```
käyttäjä ─> agent.py ─────────────> GitHub Copilot (kielimalli)
              │
              └─ fabric_mcp.py ──MCP/HTTP──> Fabric data agent (MCP-serveri) ──> PRIME DevOps -data (Lakehouse)
```

Agentilta voi kysyä PRIME:n domaineista, liiketoimintaprosesseista, capabilityistä, use caseista, vaatimuksista, User Storyistä, taskeista sekä niiden välisistä riippuvuuksista. Hierarkia on Domain → Capability → Use Case → Requirement → User Story → Task.

## Tiedostot

| Tiedosto | Tehtävä |
|---|---|
| `agent.py` | Data-agentti, jonka kielimallina on GitHub Copilot (Copilot SDK). Vain Fabric-työkalu on sallittu; Copilotin omat työkalut (komentorivi, tiedostot) on estetty. |
| `fabric_mcp.py` | MCP-client Fabricin data agentille. Hoitaa Entra ID -kirjautumisen (`az login` tai selain) ja liittää Fabric-tokenin jokaiseen pyyntöön. |
| `config.py` | Asetukset `mcp.json`- ja `.env`-tiedostoista. |
| `agent_claude.py` | Valinnainen versio, jonka kielimallina on Claude (Anthropic API). |
| `mcp.example.json` | Malli Fabricista ladattavalle `mcp.json`-tiedostolle. |

## Vaatimukset

- Python 3.11 tai uudempi
- GitHub Copilot -lisenssi
- Pääsy Fabric-workspaceen, jossa PRIME_Knowledge_DataAgent on (agentin pitää olla julkaistu)

## Asennus (kerran)

PowerShellissä:

```powershell
Set-Location "$HOME\Documents\Codes\local_agent_mcp"

# 1. Python-ympäristö
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Copilot CLI ja GitHub-kirjautuminen
winget install GitHub.Copilot
copilot
# Kirjoita CLI:ssä /login, kirjaudu selaimessa ja poistu komennolla /exit
```

Lataa `mcp.json` Fabricista (PRIME_Knowledge_DataAgent → Settings → Model Context Protocol) ja tallenna se tämän kansion juureen. Tiedosto on `.gitignore`ssa.

Jos käytät mieluummin Claudea, asenna lisäksi `.\.venv\Scripts\python.exe -m pip install -r requirements-claude.txt` ja lisää `ANTHROPIC_API_KEY` `.env`-tiedostoon.

## Käyttö

```powershell
.\.venv\Scripts\python.exe agent.py --list-tools    # testaa Fabric-yhteys
.\.venv\Scripts\python.exe agent.py                 # keskustelu
.\.venv\Scripts\python.exe agent.py "Mitä logistiikan use caseja PRIME:ssa on?"
.\.venv\Scripts\python.exe agent.py --list-models   # käytettävissä olevat Copilot-mallit
```

Ensimmäisellä käyttökerralla avautuu Microsoft-kirjautuminen Fabriciin. Keskustelussa `→`-rivit näyttävät, mitä agentti kysyi Fabricilta. Agentti muistaa keskustelun, joten jatkokysymyksiä voi esittää. Tyhjä rivi tai `exit` lopettaa.

Mallin voi vaihtaa `.env`-tiedostossa asetuksella `COPILOT_MODEL` (ks. `.env.example`).
Claude-vaihtoehto käynnistyy komennolla `.\.venv\Scripts\python.exe agent_claude.py`; se käyttää `.env`-tiedoston `CLAUDE_MODEL`-asetusta.

## Tietoturva

- `mcp.json` ja `.env` eivät mene GitHubiin. Myös `.venv` on rajattu pois Gitistä.
- Fabricin data agentin vastaukset, eli PRIME:n DevOps-sisältö, lähetetään Copilotin kielimallille käsiteltäväksi. Ne kulkevat siis Fabricin compliance-rajan ulkopuolelle organisaation GitHub Copilot -sopimuksen piiriin. Varmista, että tämä on sallittua datan luokituksen mukaan.
