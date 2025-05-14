# PoC

## Prepare

- Copy `env.sample` to `.env`
- Edit `.env` with your values

- Copy `games.json.sample` to `games.json`
- Edit `games.json` with your value

- Install `uv` with your preferred method (https://docs.astral.sh/uv/)

## Run


## Standalone CLI

```
uv run xbox-savegame-cli
```

## Discord bot

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
