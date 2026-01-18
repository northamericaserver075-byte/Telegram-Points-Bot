import os
import logging
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters, enums, idle
from pyrogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    Message
)
import asyncpg

# --- LOGGING ON ---
logging.basicConfig(level=logging.INFO)
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

# WELCOME PHOTO (Agar ye link toota, to bot Text bhej dega)
WELCOME_PIC = "https://cdn-icons-png.flaticon.com/512/4712/4712109.png" 

# ==========================================

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Premium Bot Running!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("ultra_pro_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
DB_POOL = None

# --- DATABASE SETUP ---
async def init_db():
    global DB_POOL
    try:
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        async with DB_POOL.acquire() as conn:
            await conn.execute("""CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, points INT DEFAULT 0, referrals INT DEFAULT 0);""")
            await conn.execute("""CREATE TABLE IF NOT EXISTS files (file_id TEXT PRIMARY KEY, type TEXT);""")
            await conn.execute("""CREATE TABLE IF NOT EXISTS settings (key_name TEXT PRIMARY KEY, value TEXT);""")
            
            # Default Settings
            defaults = {"video_cost": "5", "photo_cost": "2", "referral_bonus": "20", "buy_link": "https://t.me/"}
            for k, v in defaults.items():
                await conn.execute("INSERT INTO settings (key_name, value) VALUES ($1, $2) ON CONFLICT DO NOTHING", k, v)
        logger.info("✅ Database Connected!")
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")
        exit(1)

# --- HELPER FUNCTIONS ---
async def get_setting(key):
    async with DB_POOL.acquire() as conn: return await conn.fetchval("SELECT value FROM settings WHERE key_name = $1", key)

async def set_setting(key, value):
    async with DB_POOL.acquire() as conn: await conn.execute("UPDATE settings SET value = $1 WHERE key_name = $2", str(value), key)

async def get_user(user_id):
    async with DB_POOL.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not user:
            await conn.execute("INSERT INTO users (user_id, points, referrals) VALUES ($1, 10, 0)", user_id)
            return {"user_id": user_id, "points": 10, "referrals": 0}
        return user

async def update_points(user_id, points):
    async with DB_POOL.acquire() as conn: await conn.execute("UPDATE users SET points = points + $1 WHERE user_id = $2", points, user_id)

async def is_joined(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        if m.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: return True
    except: pass
    return False

# --- PREMIUM MENU (Bottom Buttons) ---
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 VIDEO"), KeyboardButton("📸 PHOTO")],
            [KeyboardButton("🥇 POINTS"), KeyboardButton("👤 PROFILE")],
            [KeyboardButton("🔗 REFER"), KeyboardButton("💰 BUY POINTS")]
        ], resize_keyboard=True
    )

# --- START HANDLER (FIXED) ---
@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    try:
        user_id = m.from_user.id
        await get_user(user_id)
        
        # Referral Logic
        if len(m.text.split()) > 1:
            try:
                ref_id = int(m.text.split()[1])
                if ref_id != user_id:
                    async with DB_POOL.acquire() as conn:
                        ref_exists = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", ref_id)
                        if ref_exists:
                            bonus = int(await get_setting("referral_bonus"))
                            await conn.execute("UPDATE users SET points = points + $1, referrals = referrals + 1 WHERE user_id = $2", bonus, ref_id)
                            try: await c.send_message(ref_id, f"🎉 **New Referral!**\n+{bonus} Points added.")
                            except: pass
            except: pass

        # Force Subscribe Logic
        if not await is_joined(user_id):
            try: link = await c.export_chat_invite_link(CHANNEL_ID)
            except: link = "https://t.me/"
            await m.reply_text("🔒 **Join Channel First!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]]))
            return

        # WELCOME MESSAGE (With Error Handling)
        caption = f"👋 **Welcome {m.from_user.first_name}!**\n\nEarn points and access premium content."
        try:
            # Koshish karega Photo bhejne ki
            await m.reply_photo(photo=WELCOME_PIC, caption=caption, reply_markup=main_menu())
        except Exception:
            # Agar Photo fail hui, to Text bhejega (Crash nahi hoga)
            await m.reply_text(caption, reply_markup=main_menu())

    except Exception as e:
        logger.error(f"Start Error: {e}")

# --- BUTTON HANDLERS ---
@bot.on_message(filters.regex("👤 PROFILE"))
async def profile(c, m):
    u = await get_user(m.from_user.id)
    await m.reply_text(f"👤 **Profile**\n🆔 `{u['user_id']}`\n💰 Points: `{u['points']}`\n👥 Referrals: `{u['referrals']}`", quote=True)

@bot.on_message(filters.regex("🥇 POINTS"))
async def points(c, m):
    u = await get_user(m.from_user.id)
    await m.reply_text(f"💰 Balance: **{u['points']}** Points", quote=True)

@bot.on_message(filters.regex("🔗 REFER"))
async def refer(c, m):
    link = f"https://t.me/{c.me.username}?start={m.from_user.id}"
    bonus = await get_setting("referral_bonus")
    await m.reply_text(f"🔗 **Refer Link:**\n`{link}`\n\nEarn **+{bonus} Points** per invite!", quote=True)

@bot.on_message(filters.regex("💰 BUY POINTS"))
async def buy(c, m):
    link = await get_setting("buy_link")
    await m.reply_text("💎 **Buy Points**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Now", url=link)]]))

@bot.on_message(filters.regex("🎬 VIDEO"))
async def get_video(c, m):
    u = await get_user(m.from_user.id)
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
    u = await get_user(m.from_user.id)
    cost = int(await get_setting("photo_cost"))
    if u['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='photo' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(u['user_id'], -cost)
                await m.reply_photo(res['file_id'], caption=f"✅ -{cost} Points")
            else: await m.reply_text("❌ No photos found!")
    else: await m.reply_text(f"❌ Need {cost} Points!")

# --- ADMIN PANEL ---
@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin(c, m):
    await m.reply_text(
        "👮‍♂️ **Admin Panel**\n\n"
        "`/add_all 100` - Sabko Points do\n"
        "`/set_refer 50` - Refer Bonus set karo\n"
        "`/set_video 10` - Video Cost set karo\n"
        "`/set_link https://..` - Buy Link set karo"
    )

@bot.on_message(filters.command("add_all") & filters.user(ADMIN_ID))
async def add_all(c, m):
    try:
        amt = int(m.text.split()[1])
        msg = await m.reply_text("⏳ Sending...")
        async with DB_POOL.acquire() as conn: await conn.execute("UPDATE users SET points = points + $1", amt)
        await msg.edit_text("✅ Done!")
    except: pass

@bot.on_message(filters.command("set_refer") & filters.user(ADMIN_ID))
async def set_r(c, m):
    try: await set_setting("referral_bonus", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_video") & filters.user(ADMIN_ID))
async def set_v(c, m):
    try: await set_setting("video_cost", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_link") & filters.user(ADMIN_ID))
async def set_l(c, m):
    try: await set_setting("buy_link", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def index(c, m):
    try:
        fid, ftype = (m.video.file_id, "video") if m.video else (m.photo.file_id, "photo")
        async with DB_POOL.acquire() as conn:
            await conn.execute("INSERT INTO files (file_id, type) VALUES ($1, $2) ON CONFLICT (file_id) DO NOTHING", fid, ftype)
            await m.react(emoji="🔥")
    except: pass

# --- STARTUP ---
async def start_services():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    await init_db()
    await bot.start()
    await idle()
    await bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
