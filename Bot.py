import os
import sqlite3
import random
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5304912608

CHANNELS = ["@earningloots2612", "@doingdot"]
MIN_WITHDRAW = 20
TASK_REWARD = 4

db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
 user_id INTEGER PRIMARY KEY,
 public_id INTEGER UNIQUE,
 balance REAL DEFAULT 0,
 last_daily TEXT DEFAULT '',
 joined_at TEXT DEFAULT ''
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS tasks(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT,
 desc TEXT,
 active INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS submissions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 task_id INTEGER,
 proof TEXT,
 status TEXT DEFAULT 'pending'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS withdrawals(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 amount REAL,
 upi TEXT,
 status TEXT DEFAULT 'pending'
)
""")
db.commit()


def today():
    return time.strftime("%Y-%m-%d")


async def safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        raise e


def get_public_id():
    while True:
        rid = random.randint(100000, 999999)
        cur.execute("SELECT user_id FROM users WHERE public_id=?", (rid,))
        if not cur.fetchone():
            return rid


def ensure_user(user_id):
    cur.execute("SELECT public_id FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        rid = get_public_id()
        joined = time.strftime("%d-%m-%Y %I:%M %p")
        cur.execute(
            "INSERT INTO users(user_id, public_id, joined_at) VALUES(?,?,?)",
            (user_id, rid, joined),
        )
        db.commit()


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Daily Signup", callback_data="daily")],
        [
            InlineKeyboardButton("💰 Wallet", callback_data="wallet"),
            InlineKeyboardButton("📋 Tasks", callback_data="tasks"),
        ],
        [InlineKeyboardButton("🏧 Withdraw", callback_data="withdraw")],
    ])


async def is_joined(user_id, context):
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id)

    if not await is_joined(user.id, context):
        buttons = [
            [InlineKeyboardButton("Join Channel 1", url="https://t.me/earningloots2612")],
            [InlineKeyboardButton("Join Channel 2", url="https://t.me/doingdot")],
            [InlineKeyboardButton("✅ I Joined", callback_data="check_join")],
        ]
        await update.message.reply_text(
            "⚠️ Bot use karne ke liye pehle dono channels join karo.",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await update.message.reply_text(
    "🎉 Welcome to Task Hub Rewards 🎉\n\n"
    "💸 Complete daily tasks and earn exciting rewards instantly!\n\n"
    "🔥 Features:\n"
    "• Random Daily Rewards\n"
    "• Referral Earnings\n"
    "• Wallet System\n"
    "• Fast Withdrawals\n"
    "• Trusted Community\n\n"
    "📢 Before starting, please join our official channels to unlock the bot.\n\n"
    "✅ After joining, click the “Joined” button below and start earning rewards today 🚀",
    reply_markup=menu()
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    ensure_user(user_id)

    if query.data == "check_join":
        if await is_joined(user_id, context):
            await safe_edit(query, "✅ Verified Successfully", reply_markup=menu())
        else:
            await safe_edit(query, "❌ Abhi dono channels join nahi hue.")
        return

    if not await is_joined(user_id, context):
        await safe_edit(query, "⚠️ Pehle dono channels join karo.")
        return

    if query.data == "daily":
        cur.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
        last = cur.fetchone()[0]

        if last == today():
            await safe_edit(query, "✅ Aaj ka daily reward already le chuke ho.", reply_markup=menu())
            return

        reward = random.randint(1, 5)
        cur.execute(
            "UPDATE users SET balance=balance+?, last_daily=? WHERE user_id=?",
            (reward, today(), user_id),
        )
        db.commit()

        await safe_edit(
            query,
            f"🎉 Daily reward claimed!\n💸 ₹{reward} wallet me add hua.",
            reply_markup=menu(),
        )

    elif query.data == "wallet":
        cur.execute("SELECT balance, public_id FROM users WHERE user_id=?", (user_id,))
        bal, public_id = cur.fetchone()
        await safe_edit(
            query,
            f"🆔 Your ID: {public_id}\n💰 Wallet Balance: ₹{bal}",
            reply_markup=menu(),
        )

    elif query.data == "tasks":
        cur.execute("SELECT id,title,desc FROM tasks WHERE active=1 ORDER BY id DESC")
        tasks = cur.fetchall()

        if not tasks:
            await safe_edit(query, "❌ Abhi koi task available nahi hai.", reply_markup=menu())
            return

        keyboard = []
        for t in tasks:
            keyboard.append([
                InlineKeyboardButton(
                    f"ID {t[0]} | {t[1]} - ₹{TASK_REWARD}",
                    callback_data=f"task_{t[0]}",
                )
            ])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])

        await safe_edit(query, "📋 Available Tasks", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("task_"):
        task_id = int(query.data.split("_")[1])
        cur.execute("SELECT title,desc FROM tasks WHERE id=? AND active=1", (task_id,))
        task = cur.fetchone()

        if not task:
            await safe_edit(query, "❌ Task not found.", reply_markup=menu())
            return

        context.user_data["proof_task"] = task_id
        await safe_edit(query, f"📌 Task: {task[0]}\n\n{task[1]}\n\n📤 Proof bhejo.")

    elif query.data == "withdraw":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]

        if bal < MIN_WITHDRAW:
            await safe_edit(
                query,
                f"❌ Minimum withdrawal ₹{MIN_WITHDRAW} hai.\n\nYour Balance: ₹{bal}",
                reply_markup=menu(),
            )
            return

        context.user_data["withdraw"] = True
        await safe_edit(query, "🏧 Withdrawal Request\n\n💳 Apna UPI ID bhejo.\nExample: yourname@upi")

    elif query.data.startswith("approve_task_"):
        if user_id != ADMIN_ID:
            return

        sid = int(query.data.split("_")[2])
        cur.execute("SELECT user_id,status FROM submissions WHERE id=?", (sid,))
        row = cur.fetchone()

        if row and row[1] == "pending":
            cur.execute("UPDATE submissions SET status='approved' WHERE id=?", (sid,))
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (TASK_REWARD, row[0]))
            db.commit()

            await context.bot.send_message(row[0], f"✅ Task approved.\n₹{TASK_REWARD} added.")
            await safe_edit(query, "✅ Task Approved")

    elif query.data.startswith("reject_task_"):
        if user_id != ADMIN_ID:
            return

        sid = int(query.data.split("_")[2])
        cur.execute("SELECT user_id FROM submissions WHERE id=?", (sid,))
        row = cur.fetchone()

        if row:
            cur.execute("UPDATE submissions SET status='rejected' WHERE id=?", (sid,))
            db.commit()

            await context.bot.send_message(row[0], "❌ Task rejected.")
            await safe_edit(query, "❌ Task Rejected")

    elif query.data.startswith("paid_"):
        if user_id != ADMIN_ID:
            return

        wid = int(query.data.split("_")[1])
        cur.execute("SELECT user_id,amount,status FROM withdrawals WHERE id=?", (wid,))
        row = cur.fetchone()

        if row and row[2] == "pending":
            cur.execute("UPDATE withdrawals SET status='paid' WHERE id=?", (wid,))
            cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (row[1], row[0]))
            db.commit()

            await context.bot.send_message(row[0], f"✅ Withdrawal Paid\n💸 ₹{row[1]}")
            await safe_edit(query, "✅ Withdrawal marked paid")

    elif query.data == "back":
        await safe_edit(query, "🏠 Main Menu", reply_markup=menu())


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    text = update.message.text or update.message.caption or "Photo Proof"

    if context.user_data.get("withdraw"):
        upi = text.strip()

        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]

        if bal < MIN_WITHDRAW:
            context.user_data["withdraw"] = False
            await update.message.reply_text("❌ Balance minimum withdrawal se kam hai.", reply_markup=menu())
            return

        cur.execute("INSERT INTO withdrawals(user_id,amount,upi) VALUES(?,?,?)", (user_id, bal, upi))
        wid = cur.lastrowid
        db.commit()

        context.user_data["withdraw"] = False

        await context.bot.send_message(
            ADMIN_ID,
            f"🏧 Withdrawal Request\n\n👤 User: {user_id}\n💸 Amount: ₹{bal}\n💳 UPI: {upi}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Mark Paid", callback_data=f"paid_{wid}")]
            ]),
        )

        await update.message.reply_text("✅ Withdrawal request sent to admin.", reply_markup=menu())
        return

    if "proof_task" in context.user_data:
        tid = context.user_data.pop("proof_task")

        cur.execute(
            "INSERT INTO submissions(user_id,task_id,proof) VALUES(?,?,?)",
            (user_id, tid, text),
        )
        sid = cur.lastrowid
        db.commit()

        await context.bot.send_message(
            ADMIN_ID,
            f"📋 Task Submission\n\n👤 User: {user_id}\n🆔 Submission ID: {sid}\n📌 Task ID: {tid}\n📝 Proof: {text}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_task_{sid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_task_{sid}"),
            ]]),
        )

        await update.message.reply_text("✅ Proof submitted successfully.", reply_markup=menu())


async def addtask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text("Use:\n/addtask Title | Description")
        return

    title, desc = raw.split("|", 1)
    cur.execute("INSERT INTO tasks(title,desc,active) VALUES(?,?,1)", (title.strip(), desc.strip()))
    db.commit()

    await update.message.reply_text("✅ Task Added")


async def listtasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cur.execute("SELECT id,title,desc,active FROM tasks ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("❌ No tasks found")
        return

    msg = "📋 All Tasks:\n\n"
    for r in rows:
        status = "Active" if r[3] == 1 else "Removed"
        msg += f"🆔 Task ID: {r[0]}\n📌 {r[1]}\n📝 {r[2]}\nStatus: {status}\n\n"

    await update.message.reply_text(msg[:4000])


async def removetask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 1:
        await update.message.reply_text("Use:\n/removetask 1\n/removetask 1 2 3 4")
        return

    removed = []
    not_found = []

    for arg in context.args:
        try:
            task_id = int(arg)
            cur.execute("SELECT id FROM tasks WHERE id=?", (task_id,))
            if cur.fetchone():
                cur.execute("UPDATE tasks SET active=0 WHERE id=?", (task_id,))
                removed.append(str(task_id))
            else:
                not_found.append(str(task_id))
        except Exception:
            not_found.append(arg)

    db.commit()

    msg = ""
    if removed:
        msg += "✅ Removed Tasks: " + ", ".join(removed) + "\n"
    if not_found:
        msg += "❌ Not Found: " + ", ".join(not_found)

    await update.message.reply_text(msg)


async def addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text("Use:\n/addbal USER_ID AMOUNT")
        return

    public_id = int(context.args[0])
    amount = float(context.args[1])

    cur.execute("SELECT user_id FROM users WHERE public_id=?", (public_id,))
    if not cur.fetchone():
        await update.message.reply_text("❌ User ID not found")
        return

    cur.execute("UPDATE users SET balance=balance+? WHERE public_id=?", (amount, public_id))
    db.commit()

    await update.message.reply_text(f"✅ ₹{amount} added to ID {public_id}")


async def removebal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text("Use:\n/removebal USER_ID AMOUNT")
        return

    public_id = int(context.args[0])
    amount = float(context.args[1])

    cur.execute("SELECT balance FROM users WHERE public_id=?", (public_id,))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ User ID not found")
        return

    new_balance = max(0, row[0] - amount)
    cur.execute("UPDATE users SET balance=? WHERE public_id=?", (new_balance, public_id))
    db.commit()

    await update.message.reply_text(
        f"✅ ₹{amount} removed from ID {public_id}\n💰 New Balance: ₹{new_balance}"
    )


async def setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text("Use:\n/setbal USER_ID AMOUNT")
        return

    public_id = int(context.args[0])
    amount = float(context.args[1])

    cur.execute("SELECT user_id FROM users WHERE public_id=?", (public_id,))
    if not cur.fetchone():
        await update.message.reply_text("❌ User ID not found")
        return

    cur.execute("UPDATE users SET balance=? WHERE public_id=?", (amount, public_id))
    db.commit()

    await update.message.reply_text(f"✅ Balance set to ₹{amount} for ID {public_id}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tasks WHERE active=1")
    tasks = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
    wd = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM submissions WHERE status='pending'")
    sub = cur.fetchone()[0]

    await update.message.reply_text(
        f"👥 Total Users: {users}\n📋 Active Tasks: {tasks}\n🏧 Pending Withdrawals: {wd}\n📤 Pending Task Proofs: {sub}"
    )


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT public_id, user_id, balance, joined_at
        FROM users
        ORDER BY user_id DESC
        LIMIT 30
    """)
    rows = cur.fetchall()

    msg = f"👥 Total Users: {total}\n\n"
    for r in rows:
        msg += (
            f"🆔 ID: {r[0]}\n"
            f"Telegram: {r[1]}\n"
            f"Balance: ₹{r[2]}\n"
            f"Joined: {r[3]}\n\n"
        )

    await update.message.reply_text(msg[:4000])


async def adminhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "👑 Admin Commands:\n\n"
        "/stats\n"
        "/users\n"
        "/addtask Title | Description\n"
        "/listtasks\n"
        "/removetask 1\n"
        "/removetask 1 2 3 4\n"
        "/addbal USER_ID AMOUNT\n"
        "/removebal USER_ID AMOUNT\n"
        "/setbal USER_ID AMOUNT"
    )


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN Railway Variables me add nahi hai.")

app = (
    Application.builder()
    .token(BOT_TOKEN)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", adminhelp))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("users", users))
app.add_handler(CommandHandler("addtask", addtask))
app.add_handler(CommandHandler("listtasks", listtasks))
app.add_handler(CommandHandler("removetask", removetask))
app.add_handler(CommandHandler("addbal", addbal))
app.add_handler(CommandHandler("removebal", removebal))
app.add_handler(CommandHandler("setbal", setbal))

app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, text_handler))

print("Bot Started ✅")

app.run_polling(
    poll_interval=2,
    timeout=30,
    drop_pending_updates=True,
    allowed_updates=Update.ALL_TYPES,
                   )
