Larpcord is a Discord roleplay bot engine. It can run multiple bots at once, based on definition files. Bots can even talk to each other.

Personally I use it to make AI girlfriends but maybe you have a better use case. /j

## Definitions

Each bot should have a Markdown definition file in `definitions/`, containing its name, trigger phrases, and Discord bot token. For example, the definition of a John bot in `definitions/john.md` would be:

```md
+++
name = "John"
trigger_phrases = ["john", "jon", "jone"]
token = "johns.discord.bot.token"
+++

You are John. Act as if your name was John, lorem ipsum dolor sit amet.
```

## Environment variables

- `OLLAMA_API_KEY` (required): Your [Ollama Cloud](https://ollama.com/pricing/) API key
- `FIRECRAWL_API_KEY` (optional): Your [Firecrawl](https://firecrawl.dev/) API key used to let bots search the web. If omitted, bots cannot search the web.

The easiest way to set environment variables is through an `.env` file. Create one inside the Larpcord directory. Example:

```env
OLLAMA_API_KEY=your.ollama.api.key
FIRECRAWL_API_KEY=your.firecrawl.api.key
```

## Running your bots

1. Install [uv](https://astral.sh/uv)
2. Open a terminal/command prompt window inside the Larpcord directory
3. Inside the window, type `uv run larpcord.py` and hit Enter

If there are any issues, [create an issue](https://github.com/interrrp/larpcord/issues/new/) or just contact me on Discord (`interrrp`).

## Model

I picked [Gemma 4](https://ollama.com/library/gemma4/) for its fluency and performance. You can change the model and its parameters through the [code](./larpcord.py), but I make no guarantees that it will work well.

## Context persistence

Context (also known as _conversation history_) is saved in the `contexts/` directory. For example, John's context would be in `contexts/john.db`. Context files are Python pickle files containing LangChain message objects.

## Future plans

I think it would be cool to have a web interface to manage all the bots. Maybe also supporting multiple LLM providers.

## Licensing

Larpcord is licensed under the [MIT license](./LICENSE). I'd also like to thank my friends on Discord for "stress-testing" it :P
