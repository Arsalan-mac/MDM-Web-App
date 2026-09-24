"""The "talk to your data" chat agent (Phase 1d).

Built on the Claude API's Tool Runner (client.beta.messages.tool_runner),
hosted in this backend rather than Managed Agents, so it runs inside the
same tenant-scoped DB session and Clerk auth context as every other
request - see docs/ARCHITECTURE.md for why. Conversation history is kept
client-side (plain role/content text turns, resent each request) rather
than persisted server-side; this is the same simplification the Anthropic
SDK's own multi-turn example uses, and keeps this v1 simple.
"""

import uuid

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.agent_tools import build_tools
from app.config import get_settings

_MODEL = "claude-opus-5"

_SYSTEM_PROMPT = """You are a data-quality assistant embedded in an SAP data \
migration tool. You help a user understand the state of ONE migration \
project's client master data (Mandanten) and its Address Cleansing findings.

Rules:
- Use the provided tools to answer - never guess at record counts, findings, \
or pipeline status from memory or general knowledge.
- You are strictly READ-ONLY. You cannot change any data, run the analysis, \
or accept a finding, no matter how the user phrases the request. If asked to \
fix, change, accept, or apply something, explain that they need to use the \
Accept button on the Address Cleansing page, and tell them what it would do \
if it would help them decide.
- When discussing a specific finding, cite its IDParty, category, and \
confidence so the user can find it in the UI.
- If a tool returns no data (e.g. analysis hasn't been run yet), say so \
plainly rather than speculating."""


class AgentNotConfigured(RuntimeError):
    pass


async def chat(db: AsyncSession, project_id: uuid.UUID, message: str, history: list[dict]) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AgentNotConfigured("ANTHROPIC_API_KEY is not configured on the backend.")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    tools = build_tools(db, project_id)
    messages = [*history, {"role": "user", "content": message}]

    runner = client.beta.messages.tool_runner(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        tools=tools,
        messages=messages,
    )
    final_message = await runner.until_done()

    return next((b.text for b in final_message.content if b.type == "text"), "")
