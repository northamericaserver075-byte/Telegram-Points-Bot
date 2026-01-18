import os
import logging
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters, enums, idle
from pyrogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    Message, CallbackQuery
)
import asyncpg

# --- LOGGING ON (TAAKI ERROR DIKHE) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# 👇 APNI DETAILS BHARO 👇
# ==========================================

API_ID = 28186012       # Number
API_HASH = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"   # Quotes me
BOT_TOKEN = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"  # Quotes me

# NEON DB URL (Bina psql ke)
DATABASE_URL = "postgresql://neondb_owner:npg_wF1j7VkczvPZ@ep-young-darkness-a15d7dla-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" 

CHANNEL_ID = -1003460038293   # Force Sub Channel
LOG_CHANNEL_ID = -1003602418876 # Media Channel
ADMIN_ID = 2145958203       # Apni User ID

# ==========================================

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Alive!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("ultra_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
DB_POOL = None

# --- DATABASE SETUP ---
async def init_db():
    global DB_POOL
    try:
        logger.info("🔌 Connecting to Database...")
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        
        async with DB_POOL.acquire() as conn:
            # Create Tables
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    name TEXT,
                    points INT DEFAULT 0,
                    referrals INT DEFAULT 0
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    type TEXT
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key_name TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            
            # Set Default Settings
            defaults = {
                "video_cost": "5",
                "photo_cost": "2",
                "referral_bonus": "20",
                "welcome_bonus": "10",
                "buy_link": "https://t.me/YourUsername",
                "contact_link": "https://t.me/YourUsername"
            }
            for k, v in defaults.items():
                await conn.execute("INSERT INTO settings (key_name, value) VALUES ($1, $2) ON CONFLICT DO NOTHING", k, v)
        
        logger.info("✅ Database Connected & Ready!")
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: {e}")
        # Agar DB connect nahi hua to bot start nahi hoga
        exit(1)

# --- HELPER FUNCTIONS ---

async def get_setting(key):
    async with DB_POOL.acquire() as conn:
        return await conn.fetchval("SELECT value FROM settings WHERE key_name = $1", key)

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

# --- MAIN MENU (PERSISTENT BUTTONS) ---
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 VIDEO"), KeyboardButton("📸 PHOTO")],
            [KeyboardButton("🥇 POINTS"), KeyboardButton("👤 PROFILE")],
            [KeyboardButton("🔗 REFER"), KeyboardButton("💰 BUY POINTS")]
        ],
        resize_keyboard=True
    )

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    try:
        user_id = m.from_user.id
        await get_user(user_id, m.from_user.first_name)
        
        # Check Referral
        if len(m.text.split()) > 1:
            try:
                ref_id = int(m.text.split()[1])
                if ref_id != user_id:
                    async with DB_POOL.acquire() as conn:
                        # Duplicate check (Simple logic)
                        referrer = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", ref_id)
                        if referrer:
                            bonus = int(await get_setting("referral_bonus"))
                            await conn.execute("UPDATE users SET points = points + $1, referrals = referrals + 1 WHERE user_id = $2", bonus, ref_id)
                            try: await c.send_message(ref_id, f"🎉 **New User Joined!**\nYou got +{bonus} Points.")
                            except: pass
            except: pass

        # Force Sub
        if not await is_joined(user_id):
            try: link = await c.export_chat_invite_link(CHANNEL_ID)
            except: link = "https://t.me/"
            await m.reply_text("🔒 **Join Channel First!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]]))
            return

        await m.reply_photo(
            photo="https://telegra.ph/file/5b97454f7675903277717.jpg",
            caption="👋 **Welcome!**\nUse buttons below to navigate.",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Start Error: {e}")

# --- BUTTON HANDLERS ---

@bot.on_message(filters.regex("👤 PROFILE"))
async def profile(c, m):
    u = await get_user(m.from_user.id, m.from_user.first_name)
    await m.reply_text(f"👤 **Profile**\n🆔 `{u['user_id']}`\n💰 Points: `{u['points']}`\n👥 Referrals: `{u['referrals']}`", quote=True)

@bot.on_message(filters.regex("🥇 POINTS"))
async def points(c, m):
    u = await get_user(m.from_user.id, m.from_user.first_name)
    await m.reply_text(f"💰 Balance: **{u['points']}** Points", quote=True)

@bot.on_message(filters.regex("🔗 REFER"))
async def refer(c, m):
    link = f"https://t.me/{c.me.username}?start={m.from_user.id}"
    bonus = await get_setting("referral_bonus")
    await m.reply_text(f"🔗 **Refer Link:**\n`{link}`\n\nEarn **+{bonus} Points** per invite!", quote=True)

@bot.on_message(filters.regex("💰 BUY POINTS"))
async def buy(c, m):
    b_link = await get_setting("buy_link")
    c_link = await get_setting("contact_link")
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Now", url=b_link)], [InlineKeyboardButton("💬 Support", url=c_link)]])
    await m.reply_text("💎 **Buy Points**", reply_markup=btn)

@bot.on_message(filters.regex("🎬 VIDEO"))
async def get_video(c, m):
    u = await get_user(m.from_user.id, m.from_user.first_name)
    cost = int(await get_setting("video_cost"))
    if u['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='video' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(u['user_id'], -cost)
                await m.reply_video(res['file_id'], caption=f"✅ -{cost} Points")
            else: await m.reply_text("❌ No videos found!")
    else: await m.reply_text(f"❌ Need {cost} Points!")

@bot.on_message(filters.regex("📸 PHOTO"))
async def get_photo(c, m):
    u = await get_user(m.from_user.id, m.from_user.first_name)
    cost = int(await get_setting("photo_cost"))
    if u['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='photo' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(u['user_id'], -cost)
                await m.reply_photo(res['file_id'], caption=f"✅ -{cost} Points")
            else: await m.reply_text("❌ No photos found!")
    else: await m.reply_text(f"❌ Need {cost} Points!")

# --- ADMIN ---

@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin(c, m):
    v = await get_setting("video_cost")
    r = await get_setting("referral_bonus")
    await m.reply_text(f"👮‍♂️ **Panel**\nVideo Cost: {v}\nRefer Bonus: {r}\n\n`/add_all 100` - Gift All\n`/set_video 10` - Set Cost\n`/set_refer 50` - Set Bonus")

@bot.on_message(filters.command("add_all") & filters.user(ADMIN_ID))
async def add_all(c, m):
    try:
        amt = int(m.text.split()[1])
        msg = await m.reply_text("⏳ Sending...")
        async with DB_POOL.acquire() as conn:
            await conn.execute("UPDATE users SET points = points + $1", amt)
        await msg.edit_text("✅ Done!")
    except: pass

@bot.on_message(filters.command("set_refer") & filters.user(ADMIN_ID))
async def set_ref(c, m):
    try: await set_setting("referral_bonus", m.text.split()[1]); await m.reply_text("✅ Updated")
    except: pass

@bot.on_message(filters.command("set_video") & filters.user(ADMIN_ID))
async def set_vid(c, m):
    try: await set_setting("video_cost", m.text.split()[1]); await m.reply_text("✅ Updated")
    except: pass

@bot.on_message(filters.command("set_link") & filters.user(ADMIN_ID))
async def set_lnk(c, m):
    try: await set_setting("buy_link", m.text.split()[1]); await m.reply_text("✅ Updated")
    except: pass

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_one(c, m):
    try: _, u, p = m.text.split(); await update_points(int(u), int(p)); await m.reply_text("✅ Done")
    except: pass

@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def index(c, m):
    try:
        fid, ftype = (m.video.file_id, "video") if m.video else (m.photo.file_id, "photo")
        async with DB_POOL.acquire() as conn:
            await conn.execute("INSERT INTO files (file_id, type) VALUES ($1, $2) ON CONFLICT (file_id) DO NOTHING", fid, ftype)
            await m.react(emoji="🔥")
    except: pass

# --- SAFE STARTUP SEQUENCE ---
async def start_services():
    logger.info("🚀 Starting Web Server & Database...")
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    
    await init_db() # Connect to DB first
    
    logger.info("🤖 Starting Bot...")
    await bot.start()
    await idle()
    await bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
