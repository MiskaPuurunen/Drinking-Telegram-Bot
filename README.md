# drinking-telegram-bot 🍻

A Telegram bot for tracking drinks in a group chat, logs what everyone's drinking, estimates BAC and ranks the leaderboard. Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) and SQLite.

> ⚠️ **For fun only.** BAC and "braincells remaining" values are rough estimates based on a simplified Widmark formula, not medical advice. Never use this bot (or any app) to decide whether it's safe to drive.

## Features

- **Drink logging** via inline buttons (`/add_drink`) or retroactively for a drink from earlier (`/adrink`)
- **Leaderboard** of top drinkers by total units (`/leaderboard`)
- **Personal stats** - drinks and units logged (`/stats`)
- **Estimated BAC** based on weight, sex, units consumed, and time elapsed (`/bac`)
- **Braincells remaining** - a joke stat derived from estimated BAC (`/braincells`)
- **Drinking pace** - drinks per hour, ranked, with emoji tiers (`/dph`)
- **Undo** the last logged drink (`/undo`)
- **Ping a specific person's** stats - BAC, units, first/last drink time (`/pingkarens`)
- **Admin reset** for a user's stats (`/resetuser`, admin-only)
- Preset drink types (beer, wine, shots, "Megis", alcohol-free, etc.) with pre-configured volumes/ABV

## Project Structure

```
KBOT/
├── drinkTGbot.py     # Bot logic, command handlers, main entrypoint
├── database.py       # SQLite schema + init/reset helpers
├── beers.db           # SQLite database (created automatically on first run)
└── requirements.txt   # Python dependencies
```

## Requirements

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
python-telegram-bot==20.7
```

## Setup

1. **Create a bot** with [@BotFather](https://t.me/BotFather) on Telegram and grab your API token.

2. **Add your token** in `drinkTGbot.py`:

   ```python
   .token("YOUR_TELEGRAM_API_KEY") \
   ```

3. **(Optional)Set admin user IDs** (needed for `/resetuser`):

   ```python
   ADMIN_IDS = {123123}  # replace with your Telegram user ID(s)
   ```

4. **(Optional) Set a "watched" user** for `/pingkarens`, by Telegram username (no `@`):

   ```python
   WHEREIS_USERNAME = "PERSON_YOU_WANT_TO_FOLLOW_CLOSELY_e.g_BIRTHDAY_PERSON"
   ```

5. **Run the bot:**

   ```bash
   python drinkTGbot.py
   ```

   The database (`beers.db`) and its tables are created automatically on first run via `init_db()`.

## Commands

| Command | Description |
|---|---|
| `/help` | Shows the command list |
| `/setprofile <weight_kg> <m/f>` | Sets your profile (required for BAC). DM the bot to keep this private. |
| `/add_drink` | Log a drink via inline buttons |
| `/adrink <minutes_ago> <ml> <percent>` | Log a drink retroactively, e.g. `/adrink 20 330 5` |
| `/leaderboard` | Top 10 drinkers by units |
| `/mc` | Opens the "More Commands" menu (stats, BAC, braincells, dph, undo) |
| `/stats` | Your total drinks and units |
| `/bac` | Estimated Blood Alcohol Content |
| `/braincells` | Estimated "braincells remaining" (joke stat based on BAC) |
| `/dph` | Drinking pace leaderboard (drinks per hour) |
| `/undo` | Undo your most recently logged drink |
| `/pingkarens` | Shows stats for the configured `WHEREIS_USERNAME` |
| `/resetuser <user_id>` | Admin-only: resets a user's drink totals |

## How BAC is estimated

A simplified Widmark-style formula:

```
BAC = (total_units × 8) / (weight_kg × r) − (hours_since_first_drink × 0.015)
```

where `r` is a body-water constant (0.68 for male, 0.55 for female, per the profile set with `/setprofile`). This is a rough approximation — actual BAC depends on many more factors (metabolism, food intake, drink strength accuracy, etc.).

## Data & Privacy

All data is stored locally in `beers.db` (SQLite) — nothing leaves your server. Anyone with access to the bot's host machine can read the database directly. If you're running this for a group of friends, keep that in mind before logging anything sensitive.

## Notes

- Preset drink units are defined in the `DRINKS` dict in `drinkTGbot.py` — edit volumes/ABV/names there to match what you actually drink.
- `/setprofile` is intended to be used in a DM with the bot rather than a group chat, since it's tied to your Telegram user ID regardless of chat.

## License

MIT — do whatever you want with it, drink responsibly.
