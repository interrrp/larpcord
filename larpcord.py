# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "disnake>=2.12.0",
#     "firecrawl>=4.22.2",
#     "langchain>=1.2.15",
#     "langchain-ollama>=1.1.0",
# ]
# ///

import asyncio
import pickle
import re
from itertools import batched
from os import environ
from pathlib import Path

import tomllib
from disnake import AppCmdInter, Intents, Message
from disnake.ext.commands import InteractionBot
from firecrawl import AsyncFirecrawl
from langchain.agents import create_agent
from langchain.messages import HumanMessage, ImageContentBlock
from langchain.tools import tool
from langchain_ollama import ChatOllama

MESSAGE_TEMPLATE = """
<message>
    <author>
        <id>{message.author.id}</id>
        <username>{message.author.name}</username>
        <display_name>{message.author.display_name}</display_name>
    </author>
    <channel>
        <id>{message.channel.id}</id>
        <name>{message.channel.name}</name>
        <topic>{message.channel.topic}</topic>
    </channel>
    <content>
        {message.clean_content}
    </content>
</message>
"""

SYSTEM_PROMPT_EXTENSION = """
## Messages

You are a Discord bot. Multiple users may interact with you, so each incoming message contains author info.
Do NOT respond in XML. Just respond normally with no encoding.

## Tools

As mentioned, you are given a set of tools. Use the search tool when you're not sure of information,
or are asked for recent news. Use the shell tool sparingly.

## Not responding

If you are sent a message, but:

- You do not want to respond
- You are not the person being called
- You want to leave a conversation

Say I_DO_NOT_WANT_TO_RESPOND. This will stop you from sending a reply.

## Notes

- Do not use Markdown tables
- Do not use separators (i.e. ---)
- Keep responses very short by default, as you are in a chat room
"""

env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        key, value = line.split("=")
        environ[key] = value


async def main():
    tasks = []
    for definition in Path("definitions").glob("*.md"):
        content = definition.read_text()
        parts = re.match(r"\+{3}\n([\s\S]+)\n\+{3}\n([\s\S]+)", content)
        metadata, system_prompt = tomllib.loads(parts.group(1)), parts.group(2)
        coro = launch_larper(definition.stem, metadata, system_prompt)
        task = asyncio.create_task(coro)
        tasks.append(task)

    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            for task in tasks:
                task.cancel()
            break


try:
    firecrawl_client = AsyncFirecrawl(environ["FIRECRAWL_API_KEY"])
except KeyError:
    # Firecrawl API key not provided
    firecrawl_client = None


@tool
async def search(query: str) -> str:
    """Search online for information."""
    return str((await firecrawl_client.search(query)).model_dump(mode="json"))


@tool
async def shell(cmd: str) -> str:
    """Execute a Bash command."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return f"""
<output>
    <exit_code>{proc.returncode}</exit_code>
    <stdout>
        {stdout.decode()}
    </stdout>
    <stderr>
        {stderr.decode()}
    </stderr>
</output>
"""


async def launch_larper(slug, metadata, system_prompt):
    tools = []
    if firecrawl_client is not None:
        tools.append(search)

    ollama_api_key = environ["OLLAMA_API_KEY"]
    agent = create_agent(
        model=ChatOllama(
            base_url="https://ollama.com",
            client_kwargs={"headers": {"Authorization": f"Bearer {ollama_api_key}"}},
            model="gemma4:31b-cloud",
            reasoning=False,
            temperature=1,
            top_p=0.95,
            top_k=64,
        ),
        tools=tools,
        system_prompt=system_prompt + SYSTEM_PROMPT_EXTENSION,
    )

    intents = Intents.default()
    intents.message_content = True
    bot = InteractionBot(intents=intents)

    context_path = Path(f"contexts/{slug}.db")
    try:
        context = pickle.loads(context_path.read_bytes())
    except Exception:
        context = []

    activated = True

    @bot.event
    async def on_ready():
        print(f"{bot.user} is ready")

    def should_respond_to(message: Message):
        if bot.user in message.mentions:
            return True

        for phrase in metadata["trigger_phrases"]:
            if phrase in message.content.lower():
                return True

        return False

    @bot.event
    async def on_message(message: Message):
        nonlocal activated, context

        if (
            not activated
            or message.author.id == bot.user.id
            or not should_respond_to(message)
        ):
            return

        context_message = HumanMessage(MESSAGE_TEMPLATE.format(message=message))
        for attachment in message.attachments:
            context_message.content_blocks.append(ImageContentBlock(url=attachment.url))
        context.append(context_message)

        async with message.channel.typing():
            invocation = await agent.ainvoke({"messages": context})

        context = invocation["messages"]
        response = context[-1].content

        if "I_DO_NOT_WANT_TO_RESPOND" in response:
            await message.channel.send("-# Triggered, but chose not to respond")
            return

        for chunk in batched(response, 2000):
            await message.reply("".join(chunk))

    @bot.slash_command(description=f"Clear {metadata['name']}'s memory")
    async def clear_context(interaction: AppCmdInter):
        context.clear()
        context_path.write_bytes(pickle.dumps(context))
        await interaction.response.send_message("Cleared context")

    @bot.slash_command(description=f"Make {metadata['name']} stop responding")
    async def deactivate(interaction: AppCmdInter):
        nonlocal activated
        if not activated:
            await interaction.response.send_message("I was already deactivated")
            return
        activated = False
        await interaction.response.send_message("Deactivated")

    @bot.slash_command(description=f"Make {metadata['name']} start responding")
    async def activate(interaction: AppCmdInter):
        nonlocal activated
        if activated:
            await interaction.response.send_message("I was already activated")
            return
        activated = True
        await interaction.response.send_message("Activated")

    await bot.start(metadata["token"])


asyncio.run(main())
