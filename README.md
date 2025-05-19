# Spark Save downloader discord bot
### a discord bot that allows anyone on any platform to download their game saves (project spark and others) from xbox live and use it somewhere else
currently a bot is active in our [discord](https://discord.gg/zGGpFp8fSm). please join for instructions on how to use.

## Preparation

- Copy `env.sample` to `.env`
- Edit `.env` with your values

- Copy `games.json.sample` to `games.json`
- Edit `games.json` with your value

- Install `uv` with your preferred method (https://docs.astral.sh/uv/)

## Run
you can run this program as a bot or as a standalone CLI program.

- ### Standalone CLI

```
uv run xbox-savegame-cli
```

- ### Discord bot

```
uv run xbox-savegame-discord_bot
```

## Docker

Regular use (will use latest published image from main branch):

```
# Start
docker compose up -d
# Stop
docker compose down
```

Development (build from current local code)

```
# Start
docker compose -f docker-compose.development.yml up -d
# Stop
docker compose -f docker-compose.development.yml down
```

---
> this project was a joint effort between project spark community and disney infinity community.
> made by tuxuser🐧 and lionthd🦁 
