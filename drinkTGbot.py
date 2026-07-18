import asyncio
import sqlite3
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TimedOut
from datetime import datetime, timezone, timedelta


from database import init_db, DB_PATH, reset_user_by_id

#DRINKS
DRINKS = {
    "beer_033_5": ("0.33L 5%", 330, 5),
    "beer_05_5": ("0.5L 5%", 500, 5),
    "beer_03_8": ("0.3L 8%", 300, 8),
    "beer_05_8": ("0.5L 8%", 500, 8),
    "wine_12_12": ("12cl 12%", 120, 12),
    "shot_45_40": ("45ml 40%", 45, 40),
    "shot_45_60": ("45ml 60%", 45, 60),
    "shotgun": ("Shotgun Beer", 330, 5),
    "alcohol_free": ("Alcohol-Free", 0, 0),
    "megis": ("Megis", 0, 0),
}



#Admin
ADMIN_IDS = {123123} # R E P L A C E

#Constants
METABOLISM_RATE = 0.015

#where is
WHEREIS_USERNAME = "PERSON_YOU_WANT_TO_FOLLOW_CLOSELY_e.g_BIRTHDAY_PERSON"  # no @


#BAC = (total_units * 8) / (body_weight * r) - (hours_since_first * 0.015)

#Commands



def utc_from_db(ts: str) -> datetime:
    if ts is None:
        return None
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    SELECT username, total_units
    FROM beers
    ORDER BY total_units DESC
    LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    if not rows:
        await safe_send_message(update.effective_message, "No drinks logged yet")
        return

    text = "Alcohol Leaderboard (units)\n\n"
    for i, (username, units) in enumerate(rows, start=1):
        text += f"{i}. {username} — {units:.2f} units\n"

    await update.effective_message.reply_text(text)



async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()



    c.execute("""
    SELECT total_drinks, total_units
    FROM beers
    WHERE user_id = ?
    """, (user.id,))

    row = c.fetchone()
    conn.close()

    if not row:
        await safe_send_message(update.effective_message, "No drinks logged yet")
        return

    drinks, units = row
    await safe_send_message(
    update.effective_message,
    f"Your stats:\nDrinks: {drinks}\nUnits: {units:.2f}"
    )



async def resetuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("Admin only.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /resetuser <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("User ID must be a number.")
        return

    reset_user_by_id(target_id)

    await update.effective_message.reply_text(
        f"User `{target_id}` has been reset.",
        parse_mode="Markdown"
    )



async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT id, units, alcohol_free
        FROM drink_log
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (user.id,))

    row = c.fetchone()
    if not row:
        conn.close()
        await update.effective_message.reply_text("Nothing to undo.")
        return

    log_id, units, alcohol_free = row

    c.execute("DELETE FROM drink_log WHERE id = ?", (log_id,))

    c.execute("""
        UPDATE beers
        SET total_drinks = total_drinks - 1,
            total_units = total_units - ?,
            alcohol_free = alcohol_free - ?
        WHERE user_id = ?
    """, (units, alcohol_free, user.id))

    conn.commit()
    conn.close()

    await update.effective_message.reply_text(
    f"Last drink undone ({units:.2f} units)."
    )



async def setprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.effective_message.reply_text("Usage: /setprofile 70 m (for someone 70kg and male)")
        return

    weight = float(context.args[0])
    sex = context.args[1].lower()

    if sex not in ("m", "f"):
        await update.effective_message.reply_text("Sex must be m or f")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO user_profile (user_id, weight, sex)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET weight=excluded.weight, sex=excluded.sex
    """, (update.effective_user.id, weight, sex))

    conn.commit()
    conn.close()

    await update.effective_message.reply_text("Profile saved.")



async def bac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT weight, sex FROM user_profile WHERE user_id = ?",
        (user.id,)
    )
    profile = c.fetchone()

    if profile is None:
        conn.close()
        await update.effective_message.reply_text(
            "Set profile first:\n/setprofile <weight_kg> <m/f>"
        )
        return

    weight, sex = profile
    r = 0.68 if sex == "m" else 0.55

    c.execute("""
        SELECT
            COALESCE(SUM(units), 0),
            MIN(created_at)
        FROM drink_log
        WHERE user_id = ?
        AND alcohol_free = 0
    """, (user.id,))

    row = c.fetchone()
    total_units = row[0]
    first_time = row[1]

    if total_units <= 0 or first_time is None:
        conn.close()
        await update.effective_message.reply_text("No alcohol drinks logged.")
        return

   
    hours = (
        datetime.now(timezone.utc)
        - utc_from_db(first_time)
    ).total_seconds() / 3600

    METABOLISM_RATE = 0.015

    bac_value = (total_units * 8) / (weight * r)
    bac_value -= hours * METABOLISM_RATE
    bac_value = max(0, bac_value)

    conn.close()

    await update.effective_message.reply_text(
        f"Estimated BAC: {bac_value:.3f}\n"
        f"Alcohol units: {total_units:.1f}\n"
        f"Time drinking: {hours:.1f}h\n"
        f"Estimate only"
    )



async def add_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(text=name, callback_data=key)]
        for key, (name, _, _) in DRINKS.items()
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "Choose your drink",
        reply_markup=reply_markup
    )



async def dph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT
            b.user_id,
            b.username,
            COUNT(dl.id) as drinks,
            MIN(dl.created_at) as first_drink
        FROM beers b
        JOIN drink_log dl ON dl.user_id = b.user_id
        WHERE dl.alcohol_free = 0
        GROUP BY b.user_id
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text("No drinking data yet")
        return

    now = datetime.now(timezone.utc)
    results = []

    for user_id, username, drinks, first_time in rows:
        if not first_time or drinks < 1:
            continue

        first = utc_from_db(first_time)
        hours = (now - first).total_seconds() / 3600
        if hours < 0.25:
            hours = 0.25

        dph_value = drinks / hours
        results.append((username, dph_value))

    if not results:
        await update.effective_message.reply_text("Not enough data")
        return

    results.sort(key=lambda x: x[1], reverse=True)

    text = "*Drinking Pace (dp/h)*\n\n"
    for i, (username, dph_value) in enumerate(results[:10], start=1):
        if dph_value >= 3:
            emoji = "🚨"
        elif dph_value >= 2:
            emoji = "🍺"
        elif dph_value >= 1:
            emoji = "🙂"
        else:
            emoji = "-"

        text += f"{i}. @{username} — {dph_value:.2f} dph {emoji}\n"

    await update.effective_message.reply_text(
    text,
    parse_mode="Markdown"
    )   



async def braincells(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT weight, sex FROM user_profile WHERE user_id = ?",
        (user.id,)
    )
    profile = c.fetchone()

    if profile is None:
        conn.close()
        await update.effective_message.reply_text(
            "Set your profile first:\n/setprofile <weight_kg> <m/f>"
        )
        return

    weight, sex = profile
    r = 0.68 if sex == "m" else 0.55

    c.execute("""
        SELECT COALESCE(SUM(units), 0), MIN(created_at)
        FROM drink_log
        WHERE user_id = ?
        AND alcohol_free = 0
    """, (user.id,))

    total_units, first_time = c.fetchone()
    conn.close()

    if total_units <= 0 or first_time is None:
        await update.effective_message.reply_text(
            "Braincells: 100%\n."
        )
        return

    hours = (
        datetime.now(timezone.utc)
        - utc_from_db(first_time)
    ).total_seconds() / 3600

    bac_value = (total_units * 8) / (weight * r)
    bac_value -= hours * METABOLISM_RATE
    bac_value = max(0, bac_value)

    brain_percent = 100 - (bac_value * 20)
    brain_percent = max(0, min(100, brain_percent))

    if brain_percent > 90:
        status = "Prime time to play pool"
    elif brain_percent > 75:
        status = "Functional probably"
    elif brain_percent > 50:
        status = "halfway there"
    elif brain_percent > 25:
        status = "skibidi \n Time to play who says it louder"
    else:
        status = "Ditch is calling"

    await update.effective_message.reply_text(
        f"Braincells remaining about: {brain_percent:.1f}%\n"
        f"{status}"
    )



async def pingkarens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = WHEREIS_USERNAME

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # find user
    c.execute("""
        SELECT user_id, total_units
        FROM beers
        WHERE username = ?
    """, (username,))
    row = c.fetchone()

    if not row:
        conn.close()
        await update.effective_message.reply_text(
            f"no clue"
        )
        return

    user_id, total_units = row

    # drinks
    c.execute("""
        SELECT created_at
        FROM drink_log
        WHERE user_id = ?
        AND alcohol_free = 0
        ORDER BY created_at ASC
    """, (user_id,))
    drinks = c.fetchall()

    # profile
    c.execute("""
        SELECT weight, sex
        FROM user_profile
        WHERE user_id = ?
    """, (user_id,))
    profile = c.fetchone()

    conn.close()

    if not drinks:
        await update.effective_message.reply_text(
            f"@{username} is suspiciously sober"
        )
        return

    first = utc_from_db(drinks[0][0])
    last = utc_from_db(drinks[-1][0])

    hours = (datetime.now(timezone.utc) - first).total_seconds() / 3600
    delta = datetime.now(timezone.utc) - last
    minutes_ago = int(delta.total_seconds() // 60)

    if minutes_ago < 60:
        last_text = f"{minutes_ago} min ago"
    else:
        hours_ago = minutes_ago // 60
        last_text = f"{hours_ago} h ago"

    bac_text = "BAC unknown"
    if profile:
        weight, sex = profile
        r = 0.68 if sex == "m" else 0.55
        bac = (total_units * 8) / (weight * r)
        bac -= hours * METABOLISM_RATE
        bac = max(0, bac)
        bac_text = f"BAC: {bac:.3f}"

    text = (
        f"*@{username}*\n"
        f"{bac_text}\n"
        f"Units: {total_units:.1f}\n"
        f"First drink: {first.strftime('%H:%M')}\n"
        f"Last drink: {last_text}\n"
        f"Mood: Vibing\n"
    )

    await update.effective_message.reply_text(text, parse_mode="Markdown")



async def safe_send_message(message_obj, text):
    if not message_obj:
        return
    chat = message_obj.chat
    for _ in range(3):  # try 3 times
        try:
            return await chat.send_message(text)
        except TimedOut:
            await asyncio.sleep(1)
    return await chat.send_message(text)



async def drink_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    drink_key = query.data
    name, ml, percent, *maybe_alcohol_free = DRINKS[drink_key]
    alcohol_free = maybe_alcohol_free[0] if maybe_alcohol_free else 0

    if drink_key == "megis":
        units = 2
    elif drink_key == "shotgun":
        units = percent * ml / 1000 * 1.5  # 1.5x
    else:
        units = 1 if alcohol_free else percent * ml / 1000

    user = query.from_user
    username = user.username or user.first_name

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO drink_log (user_id, units, alcohol_free)
        VALUES (?, ?, ?)
    """, (user.id, units, alcohol_free))

    c.execute("""
        INSERT INTO beers (user_id, username, total_drinks, total_units, alcohol_free)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            total_drinks = total_drinks + 1,
            total_units = total_units + excluded.total_units,
            alcohol_free = alcohol_free + excluded.alcohol_free,
            username = excluded.username
    """, (user.id, username, units, alcohol_free))

    conn.commit()
    conn.close()

    tag = "Alcohol-Free" if alcohol_free else "Alcohol"
    await query.edit_message_text(
        f"Added: {name}\nUnits: {units:.2f}\n{tag}"
    )



from datetime import timedelta

async def adrink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if len(context.args) != 3:
        await update.effective_message.reply_text(
            "Usage: /adrink <minutes_ago> <ml> <percent>\n"
            "Example: /adrink 20 330 5"
        )
        return

    try:
        minutes_ago = int(context.args[0])
        ml = float(context.args[1])
        percent = float(context.args[2])
        if minutes_ago < 0 or ml < 0 or percent < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("All values must be positive numbers.")
        return

    units = percent * ml / 1000 

    timestamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO drink_log (user_id, units, alcohol_free, created_at)
        VALUES (?, ?, ?, ?)
    """, (user.id, units, 0, timestamp.isoformat()))

    username = user.username or user.first_name
    c.execute("""
        INSERT INTO beers (user_id, username, total_drinks, total_units, alcohol_free)
        VALUES (?, ?, 1, ?, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET
            total_drinks = total_drinks + 1,
            total_units = total_units + excluded.total_units,
            username = excluded.username
    """, (user.id, username, units))

    conn.commit()
    conn.close()

    await safe_send_message(update.effective_message,
                        f"Added retroactive drink:\n{ml}ml, {percent}% ABV, {units:.2f} units, {minutes_ago} minutes ago")



async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Drink Tracker Bot*\n\n"
        "*Setup (DM only)*\n"
        "/setprofile <weight_kg> <m/f>\n\n"
        
        "*Commands*\n"
        "/help - Gives this info msg\n"
        "/pingkarens - Pings stats of karens\n"
        "/leaderboard – Top drinkers\n"
        "/add_drink – Log a drink\n"
        "/adrink - Input drink from before\n"
        "/mc - More Commands\n\n"
        "*At the More commands menu*\n"
        "/stats – Your stats\n"
        "/bac – Estimated Blood Alcohol Content\n"
        "/Braincells - Mental disability level\n"
        "/dph - Drinks per hour a.k.a dp/h\n"
        "/undo – Undo last inputted drink\n\n"
        
        "Tip: Set your profile in DM's for BAC to work"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")



async def mc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(text=name, callback_data=key)]
        for key, (name, _) in MC_COMMANDS.items()
    ]

    await update.effective_message.reply_text(
        "More commands:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mc_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    key = query.data
    if key in MC_COMMANDS:
        _, func = MC_COMMANDS[key]
        await func(update, context)


MC_COMMANDS = {
    "mc_stats": ("Stats", stats),
    "mc_bac": ("Blood Alcohol Content", bac),
    "mc_braincells": ("Braincells", braincells),
    "mc_dph": ("Drinks per hour", dph),
    "mc_undo": ("Undo last drink", undo),
}



# Better menu

async def set_commands(app):
    commands = [
        BotCommand("help", "Information"),
        BotCommand("pingkarens", "Ping Karens?"),
        BotCommand("leaderboard", "Show leaderboard"),
        BotCommand("add_drink", "Add a drink"),
        BotCommand("adrink", "drink consumed <x> mins ago"),
        #BotCommand("stats", "Your alcohol stats"),
        #BotCommand("undo", "Undo your last drink"),
        #BotCommand("bac", "BAC checkup"),
        #BotCommand("dph", "Drinks per hour (dp/h)"),
        #BotCommand("setprofile", "set up KG and M/F (for BAC calculation)"),
        #BotCommand("braincells", "How many braincells left"),
        BotCommand("mc", "More Commands"),
    ]
    await app.bot.set_my_commands(commands)




#main

def main():
    init_db()
    

    app = ApplicationBuilder() \
    .token("YOUR_TELEGRAM_API_KEY") \
    .read_timeout(30) \
    .write_timeout(30) \
    .build()

    app.add_handler(CommandHandler("resetuser", resetuser))

    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("dph", dph))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("add_drink", add_drink))
    app.add_handler(CommandHandler("adrink", adrink))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("bac", bac))
    app.add_handler(CommandHandler("setprofile", setprofile))
    app.add_handler(CommandHandler("pingkarens", pingkarens))
    app.add_handler(CommandHandler("braincells", braincells))
    app.add_handler(CommandHandler("mc", mc))
    app.add_handler(CallbackQueryHandler(drink_chosen, pattern='^(?!mc_)'))
    app.add_handler(CallbackQueryHandler(mc_chosen, pattern='^mc_'))

    app.post_init = set_commands

    print("running atm ")
    app.run_polling()


if __name__ == "__main__":
    main()