
# Public API Explorer Bot

A GitHub Actions-powered public API catalog discovery bot with Telegram search and details commands.

## Features

- Scans configured public API catalogs.
- Stores discovered metadata in JSON.
- Extracts OpenAPI specification information when supported.
- Searches API names, categories, descriptions and URLs.
- Shows API details, authentication metadata and available endpoints.
- Sends notifications about newly discovered entries.
- Includes basic automated tests.
- Limits downloaded response sizes and validates catalog URLs.

## Telegram Commands

- `/start` — Start the bot
- `/help` — List available commands
- `/list` — Browse collected APIs
- `/list 2` — View page 2
- `/search anime` — Search API records
- `/details 1` — Show details for record ID 1
- `/stats` — View collection statistics

## Setup

1. Create a GitHub repository.
2. Add all project files using their exact paths.
3. Open Settings → Actions → General.
4. Set Workflow permissions to Read and write permissions.
5. Create a Telegram bot with `@BotFather`.
6. Copy the bot token securely.
7. Find your Telegram chat ID.
8. Open Settings → Secrets and variables → Actions.
9. Add these repository secrets:

   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

10. Open Actions → Public API Explorer Bot.
11. Select Run workflow.
12. Inspect the workflow logs for errors.
13. Send `/start` to your Telegram bot.

## Configuration

Edit `config/settings.json` to configure:

- Catalog sources
- Request timeout
- Maximum response size
- Maximum collection size
- Maximum new records per run
- Telegram page size

## Important Limitations

GitHub Actions scheduled jobs are best-effort and may be delayed. The Telegram bot processes commands when the workflow runs; it is not a continuously running server.

This project collects API metadata. It does not guarantee that an API is online, free, unrestricted, or safe for every use case.

Authentication and pricing are reported as unknown when the sources do not establish them. Verify the provider's official documentation and terms before using an API.

The project does not automatically call every discovered API endpoint.

## Security

- Keep Telegram tokens in GitHub Secrets.
- Never commit tokens or passwords.
- Only configure trusted public HTTPS catalog sources.
- Review API provider terms and rate limits before integration.
