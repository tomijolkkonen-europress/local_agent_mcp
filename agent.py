"""PRIME-data-agentti: lokaalisti ajettava Python-agentti PRIME ERP -projektin
Azure DevOps -sisällön tutkimiseen.

Kielimalli tulee GitHub Copilotista (Copilot SDK). Data haetaan Fabricin data
agentista (PRIME_Knowledge_DataAgent), joka on MCP-serveri; tämä ohjelma on sen
MCP-client.

Käyttö:
    python agent.py                 # interaktiivinen keskustelu
    python agent.py "kysymys"       # yksittäinen kysymys
    python agent.py --list-tools    # testaa Fabric-yhteys ja listaa työkalut
    python agent.py --list-models   # listaa käytettävissä olevat Copilot-mallit
"""

import argparse
import asyncio
import json

from copilot import CopilotClient, Tool, ToolInvocation, ToolResult, convert_mcp_call_tool_result
from copilot.generated.rpc import PermissionDecisionReject
from copilot.generated.session_events import AssistantMessageData, ToolExecutionStartData
from mcp import ClientSession

from config import load_settings
from fabric_mcp import connect

SYSTEM_PROMPT = """\
You are the PRIME data agent. You help the user explore the Azure DevOps content of \
the PRIME ERP project: domains, business processes, capabilities, use cases, \
requirements, user stories, tasks, and the dependencies between them.

You get the data by calling the Fabric data agent tool, which queries PRIME DevOps \
data refined in a Fabric Lakehouse. The hierarchy is \
Domain → Capability → Use Case → Requirement → User Story → Task.

- Use the tool for every question that depends on PRIME data. Break broad or \
multi-level questions into focused sub-questions, one hierarchy level at a time, \
and combine the answers.
- Report names, IDs, states and counts exactly as the tool returns them. Never \
invent work items or data.
- If the tool returns an error, no data, or an ambiguous answer, say so plainly.
- Answer in the user's language. Use tables or lists when they make the answer \
easier to read."""


def mcp_to_copilot_tool(mcp_tool, mcp_session: ClientSession) -> Tool:
    """Kääri Fabricin MCP-työkalun Copilotin työkaluksi.

    MCP-yhteys (ja Fabric-autentikointi) pysyy tämän ohjelman hallussa;
    Copilot saa vain työkalun kuvauksen ja kutsuu sitä tämän handlerin kautta.
    """

    async def handler(invocation: ToolInvocation) -> ToolResult:
        result = await mcp_session.call_tool(mcp_tool.name, invocation.arguments or {})
        return convert_mcp_call_tool_result(result.model_dump(mode="json", by_alias=True))

    return Tool(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        parameters=mcp_tool.input_schema,
        handler=handler,
        # Lukukysely omaan dataan: ei erillistä hyväksyntää joka kutsulle.
        skip_permission=True,
    )


def deny_everything_else(request, invocation):
    # Copilot-ajoympäristössä on omia työkaluja (komentorivi, tiedostot, verkko).
    # Agentti saa käyttää vain Fabric-työkalua, joten muut pyynnöt hylätään.
    return PermissionDecisionReject(feedback="Only the PRIME Fabric data tool is allowed.")


def print_tool_calls(event) -> None:
    if isinstance(event.data, ToolExecutionStartData):
        args = json.dumps(event.data.arguments, ensure_ascii=False)
        print(f"  → {event.data.tool_name}({args})", flush=True)


async def ask(session, question: str, timeout: float) -> str:
    reply = await session.send_and_wait(question, timeout=timeout)
    if reply is None or not isinstance(reply.data, AssistantMessageData):
        return "(ei vastausta)"
    return reply.data.content or "(tyhjä vastaus)"


async def main() -> None:
    parser = argparse.ArgumentParser(description="PRIME-data-agentti (GitHub Copilot + Fabric data agent MCP)")
    parser.add_argument("question", nargs="?", help="yksittäinen kysymys (muuten interaktiivinen tila)")
    parser.add_argument("--list-tools", action="store_true", help="listaa Fabricin MCP-työkalut ja lopeta")
    parser.add_argument("--list-models", action="store_true", help="listaa Copilot-mallit ja lopeta")
    args = parser.parse_args()

    settings = load_settings()

    if args.list_tools:
        async with connect(settings) as mcp_session:
            for t in (await mcp_session.list_tools()).tools:
                print(f"{t.name}\n  {t.description}\n  schema: {json.dumps(t.input_schema, ensure_ascii=False)}")
        return

    async with CopilotClient() as client:
        # Tarkistetaan Copilot-kirjautuminen ennen Fabric-yhteyttä, jotta
        # puuttuva kirjautuminen näkyy heti eikä vasta ensimmäisessä kysymyksessä.
        auth = await client.get_auth_status()
        if not auth.isAuthenticated:
            raise SystemExit(
                f"GitHub Copilot -kirjautuminen puuttuu ({auth.statusMessage}).\n"
                "Asenna Copilot CLI ja kirjaudu kerran:\n"
                "  winget install GitHub.Copilot\n"
                "  copilot        # kirjoita /login, kirjaudu selaimessa, poistu /exit"
            )

        if args.list_models:
            for m in await client.list_models():
                print(f"{m.id:30} {m.name}")
            return

        async with connect(settings) as mcp_session:
            mcp_tools = (await mcp_session.list_tools()).tools
            tools = [mcp_to_copilot_tool(t, mcp_session) for t in mcp_tools]

            async with await client.create_session(
                model=settings.copilot_model,
                tools=tools,
                # Sallittujen työkalujen lista: vain Fabric-työkalut näkyvät mallille.
                available_tools=[t.name for t in tools],
                on_permission_request=deny_everything_else,
                system_message={"mode": "replace", "content": SYSTEM_PROMPT},
                on_event=print_tool_calls,
            ) as session:
                if args.question:
                    print(await ask(session, args.question, settings.answer_timeout_s))
                    return

                print(f"PRIME-data-agentti valmis. Työkalut: {', '.join(t.name for t in tools)}")
                print("Kirjoita kysymys (tyhjä rivi tai 'exit' lopettaa).\n")
                while True:
                    try:
                        question = (await asyncio.to_thread(input, "kysymys> ")).strip()
                    except (EOFError, KeyboardInterrupt):
                        break
                    if not question or question.lower() in {"exit", "quit"}:
                        break
                    print(f"\n{await ask(session, question, settings.answer_timeout_s)}\n")


if __name__ == "__main__":
    asyncio.run(main())
