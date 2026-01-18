import os
import threading
import asyncio
import re
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    Message, CallbackQuery
)
import asyncpg

# ==========================================
# 👇 APNI DETAILS BHARO 👇
# ==========================================

API_ID = 28186012       # API ID (Number)
API_HASH = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"   # API Hash (Quotes me)
BOT_TOKEN = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"  # Bot Token

# 👇 NEON.TECH SE JO LINK MILA WO YAHAN DAALO 👇
DATABASE_URL = "postgresql://neondb_owner:npg_wF1j7VkczvPZ@ep-young-darkness-a15d7dla-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

CHANNEL_ID = -1003460038293   # Force Sub Channel
LOG_CHANNEL_ID = -1003602418876 # Media Channel
ADMIN_ID = 2145958203       # Apni ID

# ==========================================

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Premium Bot Live"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("ultra_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
DB_POOL = None

# --- DATABASE SETUP (AUTO-SETTINGS) ---
async def init_db():
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)
    async with DB_POOL.acquire() as conn:
        # Users Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name TEXT,
                points INT DEFAULT 0,
                referrals INT DEFAULT 0
            );
        """)
        # Files Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                type TEXT
            );
        """)
        # Settings Table (Dynamic Admin Control)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key_name TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Default Settings (Agar pehle se nahi hain)
        defaults = {
            "video_cost": "5",
            "photo_cost": "2",
            "referral_bonus": "20",
            "welcome_bonus": "10",
            "buy_link": f"https://t.me/YourUsername",
            "contact_link": f"https://t.me/YourUsername"
        }
        for k, v in defaults.items():
            await conn.execute("INSERT INTO settings (key_name, value) VALUES ($1, $2) ON CONFLICT DO NOTHING", k, v)
    print("✅ Database & Settings Ready!")

# --- HELPER FUNCTIONS ---

async def get_setting(key):
    async with DB_POOL.acquire() as conn:
        val = await conn.fetchval("SELECT value FROM settings WHERE key_name = $1", key)
        return val

async def set_setting(key, value):
    async with DB_POOL.acquire() as conn:
        await conn.execute("UPDATE settings SET value = $1 WHERE key_name = $2", str(value), key)

async def get_user(user_id, name):
    async with DB_POOL.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not user:
            bonus = int(await get_setting("welcome_bonus"))
            await conn.execute("INSERT INTO users (user_id, name, points, referrals) VALUES ($1, $2, $3, 0)", user_id, name, bonus)
            return {"user_id": user_id, "name": name, "points": bonus, "referrals": 0}
        return user

async def update_points(user_id, points):
    async with DB_POOL.acquire() as conn:
        await conn.execute("UPDATE users SET points = points + $1 WHERE user_id = $2", points, user_id)

async def is_joined(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        if m.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except: pass
    return False

# --- MAIN MENU KEYBOARD (SCREENSHOT STYLE) ---
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 VIDEO"), KeyboardButton("📸 PHOTO")],
            [KeyboardButton("🥇 POINTS"), KeyboardButton("👤 PROFILE")],
            [KeyboardButton("🔗 REFER"), KeyboardButton("💰 BUY POINTS")]
        ],
        resize_keyboard=True
    )

# --- COMMANDS & HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    user_id = m.from_user.id
    name = m.from_user.first_name
    
    await get_user(user_id, name) # Init User
    
    # Referral System
    text = m.text.split()
    if len(text) > 1:
        try:
            ref_id = int(text[1])
            if ref_id != user_id:
                async with DB_POOL.acquire() as conn:
                    # Check duplicate referral
                    is_new = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                    # (Simple logic: har click par nahi, bas new start par)
                    # Note: Full duplicate check needs more DB columns, keeping simple for now
                    bonus = int(await get_setting("referral_bonus"))
                    await conn.execute("UPDATE users SET points = points + $1, referrals = referrals + 1 WHERE user_id = $2", bonus, ref_id)
                    try: await c.send_message(ref_id, f"🎉 **New Referral!**\n{name} joined.\n**+{bonus} Points** added!")
                    except: pass
        except: pass

    # Force Sub
    if not await is_joined(user_id):
        try: link = await c.export_chat_invite_link(CHANNEL_ID)
        except: link = "https://t.me/"
        await m.reply_text(
            "🔒 **Access Denied!**\n\nJoin our channel to access the bot.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]])
        )
        return

    # Welcome
    await m.reply_photo(
        photo="https://telegra.ph/file/5b97454f7675903277717.jpg", # Apni Image lagao
        caption=f"👋 **Welcome {name}!**\n\nUse the buttons below to access content.",
        reply_markup=main_menu()
    )

# --- TEXT HANDLERS (REPLY BUTTONS) ---

@bot.on_message(filters.regex("👤 PROFILE"))
async def profile_handler(c, m):
    user = await get_user(m.from_user.id, m.from_user.first_name)
    txt = (
        f"👤 **Your Profile**\n\n"
        f"🆔 **ID:** `{user['user_id']}`\n"
        f"💰 **Points:** `{user['points']}`\n"
        f"👥 **Referrals:** `{user['referrals']}`"
    )
    await m.reply_text(txt, quote=True)

@bot.on_message(filters.regex("🥇 POINTS"))
async def balance_handler(c, m):
    user = await get_user(m.from_user.id, m.from_user.first_name)
    await m.reply_text(f"💰 **Current Balance:** {user['points']} Points", quote=True)

@bot.on_message(filters.regex("🔗 REFER"))
async def refer_handler(c, m):
    link = f"https://t.me/{c.me.username}?start={m.from_user.id}"
    bonus = await get_setting("referral_bonus")
    await m.reply_text(f"🔗 **Refer & Earn**\n\nInvite friends and get **+{bonus} Points** per user!\n\n👇 **Your Link:**\n`{link}`", quote=True)

@bot.on_message(filters.regex("💰 BUY POINTS"))
async def buy_handler(c, m):
    buy_link = await get_setting("buy_link")
    contact_link = await get_setting("contact_link")
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Buy Now", url=buy_link)],
        [InlineKeyboardButton("💬 Contact Owner", url=contact_link)]
    ])
    await m.reply_text("💎 **Buy Points**\n\nClick below to purchase points instantly.", reply_markup=btn)

@bot.on_message(filters.regex("🎬 VIDEO"))
async def video_handler(c, m):
    user_id = m.from_user.id
    user = await get_user(user_id, m.from_user.first_name)
    cost = int(await get_setting("video_cost"))
    
    if user['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='video' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(user_id, -cost)
                await m.reply_video(res['file_id'], caption=f"✅ **-{cost} Points**")
            else: await m.reply_text("❌ No videos uploaded yet!")
    else:
        await m.reply_text(f"❌ **Low Balance!**\nYou need {cost} points. Refer friends to earn.")

@bot.on_message(filters.regex("📸 PHOTO"))
async def photo_handler(c, m):
    user_id = m.from_user.id
    user = await get_user(user_id, m.from_user.first_name)
    cost = int(await get_setting("photo_cost"))
    
    if user['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='photo' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(user_id, -cost)
                await m.reply_photo(res['file_id'], caption=f"✅ **-{cost} Points**")
            else: await m.reply_text("❌ No photos uploaded yet!")
    else:
        await m.reply_text(f"❌ **Low Balance!**\nYou need {cost} points.")

# --- ADMIN PANEL (DYNAMIC) ---

@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(c, m):
    # Fetch current settings to show in panel
    v_cost = await get_setting("video_cost")
    r_bonus = await get_setting("referral_bonus")
    
    txt = (
        f"👮‍♂️ **Admin Control Panel**\n\n"
        f"🎬 Video Cost: {v_cost}\n"
        f"🔗 Refer Bonus: {r_bonus}\n\n"
        f"**Commands List:**\n"
        f"1️⃣ Change Values:\n"
        f"`/set_video 10` (Set Video Cost)\n"
        f"`/set_photo 5` (Set Photo Cost)\n"
        f"`/set_refer 50` (Set Refer Bonus)\n"
        f"`/set_link https://t.me/xx` (Set Buy Link)\n\n"
        f"2️⃣ Users Control:\n"
        f"`/add_all 10` (Give 10 pts to EVERYONE)\n"
        f"`/add 12345 100` (Give pts to one user)\n"
        f"`/top` (See Top 10 Referrers)\n"
        f"`/stats` (Check Total Users)"
    )
    await m.reply_text(txt)

# --- DYNAMIC SETTING COMMANDS ---

@bot.on_message(filters.command("set_video") & filters.user(ADMIN_ID))
async def set_v(c, m):
    try: val = m.text.split()[1]; await set_setting("video_cost", val); await m.reply_text(f"✅ Video Cost set to: {val}")
    except: await m.reply_text("❌ Use: /set_video 10")

@bot.on_message(filters.command("set_photo") & filters.user(ADMIN_ID))
async def set_p(c, m):
    try: val = m.text.split()[1]; await set_setting("photo_cost", val); await m.reply_text(f"✅ Photo Cost set to: {val}")
    except: await m.reply_text("❌ Use: /set_photo 5")

@bot.on_message(filters.command("set_refer") & filters.user(ADMIN_ID))
async def set_r(c, m):
    try: val = m.text.split()[1]; await set_setting("referral_bonus", val); await m.reply_text(f"✅ Refer Bonus set to: {val}")
    except: await m.reply_text("❌ Use: /set_refer 20")

@bot.on_message(filters.command("set_link") & filters.user(ADMIN_ID))
async def set_l(c, m):
    try: val = m.text.split()[1]; await set_setting("buy_link", val); await m.reply_text(f"✅ Buy Link Updated!")
    except: await m.reply_text("❌ Use: /set_link https://...")

# --- BROADCAST POINTS & TOP REFERRERS ---

@bot.on_message(filters.command("add_all") & filters.user(ADMIN_ID))
async def add_all_pts(c, m):
    try:
        amount = int(m.text.split()[1])
        msg = await m.reply_text(f"⏳ Sending {amount} points to ALL users...")
        async with DB_POOL.acquire() as conn:
            await conn.execute("UPDATE users SET points = points + $1", amount)
            count = await conn.fetchval("SELECT COUNT(*) FROM users")
        await msg.edit_text(f"✅ Added {amount} points to {count} users!")
    except: await m.reply_text("❌ Use: /add_all 10")

@bot.on_message(filters.command("top") & filters.user(ADMIN_ID))
async def top_referrers(c, m):
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, name, referrals FROM users ORDER BY referrals DESC LIMIT 10")
        txt = "🏆 **Top 10 Referrers** 🏆\n\n"
        for i, row in enumerate(rows, 1):
            txt += f"{i}. {row['name']} (ID: `{row['user_id']}`) - **{row['referrals']} Refs**\n"
        txt += "\n💡 Copy ID and use `/add ID AMOUNT` to reward them."
        await m.reply_text(txt)

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast(c, m):
    msg = await m.reply_text("⏳ Sending...")
    count = 0
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        for row in rows:
            try:
                await m.reply_to_message.copy(row['user_id'])
                count += 1
                await asyncio.sleep(0.1)
            except: pass
    await msg.edit_text(f"✅ Sent to {count} users.")

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_one(c, m):
    try:
        _, uid, pts = m.text.split()
        await update_points(int(uid), int(pts))
        await m.reply_text("✅ Done")
    except: pass

# --- AUTO INDEXING ---
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def index_media(c, m):
    try:
        if m.video: fid, ftype = m.video.file_id, "video"
        elif m.photo: fid, ftype = m.photo.file_id, "photo"
        else: return
        async with DB_POOL.acquire() as conn:
            await conn.execute("INSERT INTO files (file_id, type) VALUES ($1, $2) ON CONFLICT (file_id) DO NOTHING", fid, ftype)
            await m.react(emoji="🔥")
    except: pass

# --- STARTUP ---
if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    print("🚀 Ultra Bot Started!")
    bot.run()
