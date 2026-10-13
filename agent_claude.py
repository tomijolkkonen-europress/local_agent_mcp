"""PRIME-data-agentin vaihtoehtoinen versio, jossa kielimallina on Claude
(Anthropic API). Pääversio on agent.py (GitHub Copilot). Vaatii ANTHROPIC_API_KEY:n
ja paketin `anthropic[mcp]`.

Käyttö:
    python agent_claude.py                 # interaktiivinen keskustelu
    python agent_claude.py "kysymys"       # yksittäinen kysymys
    python agent_claude.py --list-tools    # testaa MCP-yhteys ja listaa työkalut
"""

import argparse
import asyncio
import json
import os

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from anthropic.types.beta import BetaMessageParam

from config import Settings, load_settings
from fabric_mcp import connect

SYSTEM_PROMPT = """\
You are a data assistant running on the user's machine. You answer questions about \
the organization's data by calling the Fabric data agent tool, which queries data in \
Microsoft Fabric and returns grounded answers.

- Use the tool for any question that depends on the organization's data. You can call \
it several times to break a complex question into focused sub-questions.
- Report figures exactly as the tool returns them, and say which question you asked \
the tool when it helps the user judge the answer. Never invent data.
- If the tool returns an error, no data, or an ambiguous answer, say so plainly.
- Answer in the user's language."""

# Palvelinpuolen fallback: jos turvaluokitin hylkää pyynnön, API ohjaa sen
# automaattisesti toiselle mallille.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _print_tool_calls(message) -> None:
    for block in message.content:
        if block.type == "tool_use":
            print(f"  → {block.name}({json.dumps(block.input, ensure_ascii=False)})")


async def run_turn(
    client: AsyncAnthropic,
    settings: Settings,
    tools: list,
    messages: list[BetaMessageParam],
) -> str:
    """Ajaa yhden käyttäjän vuoron loppuun ja lisää sen viestit `messages`-historiaan."""
    runner = client.beta.messages.tool_runner(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": settings.effort},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )

    last = None
    async for message in runner:
        last = message
        _print_tool_calls(message)
        # Runner pitää oman kopionsa historiasta, joten peilataan se tänne,
        # jotta seuraava kysymys näkee koko keskustelun. Sisältö lisätään
        # muuttamattomana (myös thinking-lohkot).
        messages.append({"role": "assistant", "content": message.content})
        tool_response = await runner.generate_tool_call_response()
        if tool_response is not None:
            messages.append(tool_response)

    if last is None:
        return "(ei vastausta)"
    if last.stop_reason == "refusal":
        return "(Malli kieltäytyi vastaamasta tähän pyyntöön.)"

    text = "\n".join(b.text for b in last.content if b.type == "text").strip()
    if last.stop_reason == "max_tokens":
        text += "\n\n(Vastaus katkesi max_tokens-rajaan.)"
    return text or "(tyhjä vastaus)"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Lokaali data-agentti Fabricin data agentin päällä")
    parser.add_argument("question", nargs="?", help="yksittäinen kysymys (muuten interaktiivinen tila)")
    parser.add_argument("--list-tools", action="store_true", help="listaa MCP-serverin työkalut ja lopeta")
    args = parser.parse_args()

    settings = load_settings()
    if not args.list_tools and not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        raise SystemExit("ANTHROPIC_API_KEY puuttuu: kopioi .env.example -> .env ja lisää avain.")

    async with connect(settings) as session:
        mcp_tools = (await session.list_tools()).tools

        if args.list_tools:
            for t in mcp_tools:
                print(f"{t.name}\n  {t.description}\n  schema: {json.dumps(t.input_schema, ensure_ascii=False)}")
            return

        tools = [async_mcp_tool(t, session) for t in mcp_tools]
        client = AsyncAnthropic()
        messages: list[BetaMessageParam] = []

        if args.question:
            messages.append({"role": "user", "content": args.question})
            print(await run_turn(client, settings, tools, messages))
            return

        print(f"Yhdistetty. Työkalut: {', '.join(t.name for t in mcp_tools)}")
        print("Kirjoita kysymys (tyhjä rivi tai 'exit' lopettaa).\n")
        while True:
            try:
                question = (await asyncio.to_thread(input, "> ")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question.lower() in {"exit", "quit"}:
                break
            messages.append({"role": "user", "content": question})
            print(f"\n{await run_turn(client, settings, tools, messages)}\n")


if __name__ == "__main__":
    asyncio.run(main())
