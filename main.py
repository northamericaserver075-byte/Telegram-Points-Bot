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

# --- LOGGING ---
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

LOG_CHANNEL_ID = -1003602418876 # Media Channel
ADMIN_ID = 2145958203       # Apni User ID

# WELCOME PHOTO
WELCOME_PIC = "https://cdn-icons-png.flaticon.com/512/4712/4712109.png"

# ==========================================

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT SETUP ---
bot = Client("final_dynamic_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
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
            
            defaults = {
                "video_cost": "5", "photo_cost": "2", "referral_bonus": "20", 
                "welcome_bonus": "10", "buy_link": "https://t.me/", 
                "contact_link": "https://t.me/", "force_channel": "0" 
            }
            for k, v in defaults.items():
                await conn.execute("INSERT INTO settings (key_name, value) VALUES ($1, $2) ON CONFLICT DO NOTHING", k, v)
        logger.info("✅ Database Ready!")
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
            bonus = int(await get_setting("welcome_bonus"))
            await conn.execute("INSERT INTO users (user_id, points, referrals) VALUES ($1, $2, 0)", user_id, bonus)
            return {"user_id": user_id, "points": bonus, "referrals": 0}
        return user

async def update_points(user_id, points):
    async with DB_POOL.acquire() as conn: await conn.execute("UPDATE users SET points = points + $1 WHERE user_id = $2", points, user_id)

async def is_joined(user_id):
    if user_id == ADMIN_ID: return True
    # Fetch Channel ID from DB
    channel_id = await get_setting("force_channel")
    if not channel_id or channel_id == "0": return True # Agar set nahi hai to skip karo
    
    try:
        m = await bot.get_chat_member(int(channel_id), user_id)
        if m.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: return True
    except: pass
    return False

# --- KEYBOARDS ---
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 VIDEO"), KeyboardButton("📸 PHOTO")],
            [KeyboardButton("🥇 POINTS"), KeyboardButton("👤 PROFILE")],
            [KeyboardButton("🔗 REFER"), KeyboardButton("💰 GET POINTS")]
        ], resize_keyboard=True
    )

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm_cast"), InlineKeyboardButton("📊 Statistics", callback_data="adm_stats")],
        # NEW BUTTON: SET CHANNEL
        [InlineKeyboardButton("⚙️ Set Channel", callback_data="set_ch"), InlineKeyboardButton("⚙️ Welcome Bonus", callback_data="set_w")],
        [InlineKeyboardButton("⚙️ Video Cost", callback_data="set_v"), InlineKeyboardButton("⚙️ Photo Cost", callback_data="set_p")],
        [InlineKeyboardButton("⚙️ Refer Bonus", callback_data="set_r"), InlineKeyboardButton("🎁 Gift All Pts", callback_data="adm_all")],
        [InlineKeyboardButton("➕ Add User Pts", callback_data="adm_add"), InlineKeyboardButton("🔗 Buy Link", callback_data="set_l")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="close")]
    ])

# --- COMMANDS ---
@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    try:
        user_id = m.from_user.id
        await get_user(user_id)
        
        # Referral
        if len(m.text.split()) > 1:
            try:
                ref_id = int(m.text.split()[1])
                if ref_id != user_id:
                    async with DB_POOL.acquire() as conn:
                        if await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", ref_id):
                            bonus = int(await get_setting("referral_bonus"))
                            await conn.execute("UPDATE users SET points = points + $1, referrals = referrals + 1 WHERE user_id = $2", bonus, ref_id)
                            try: await c.send_message(ref_id, f"🎉 **New Referral!**\n+{bonus} Points.")
                            except: pass
            except: pass

        # Force Subscribe Logic (Dynamic)
        if not await is_joined(user_id):
            channel_id = await get_setting("force_channel")
            try: link = await c.export_chat_invite_link(int(channel_id))
            except: link = "https://t.me/"
            await m.reply_text("🔒 **Join Channel First!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]]))
            return

        caption = f"👋 **Welcome {m.from_user.first_name}!**\n\nUse buttons below to access content."
        try: await m.reply_photo(WELCOME_PIC, caption=caption, reply_markup=main_menu())
        except: await m.reply_text(caption, reply_markup=main_menu())
    except: pass

# --- USER BUTTONS ---
@bot.on_message(filters.regex("👤 PROFILE"))
async def profile(c, m):
    u = await get_user(m.from_user.id)
    await m.reply_text(f"👤 **Profile**\n🆔 `{u['user_id']}`\n💰 Points: `{u['points']}`\n👥 Referrals: `{u['referrals']}`", quote=True)

@bot.on_message(filters.regex("🥇 POINTS"))
async def points(c, m):
    u = await get_user(m.from_user.id)
    await m.reply_text(f"💰 Balance: **{u['points']}** Points\n\n💡 _Refer or buy now to get more Points!_", quote=True)

@bot.on_message(filters.regex("🔗 REFER"))
async def refer(c, m):
    link = f"https://t.me/{c.me.username}?start={m.from_user.id}"
    bonus = await get_setting("referral_bonus")
    await m.reply_text(f"🔗 **Refer & Earn**\n\nInvite friends & get **+{bonus} Points**!\n\n👇 **Your Link:**\n`{link}`", quote=True)

@bot.on_message(filters.regex("💰 GET POINTS"))
async def buy(c, m):
    l = await get_setting("buy_link")
    cl = await get_setting("contact_link")
    await m.reply_text("💎 **Get Points**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Now", url=l), InlineKeyboardButton("💬 Contact Owner", url=cl)]]))

@bot.on_message(filters.regex("🎬 VIDEO"))
async def video(c, m):
    u = await get_user(m.from_user.id)
    cost = int(await get_setting("video_cost"))
    if u['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='video' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(u['user_id'], -cost)
                await m.reply_video(res['file_id'], caption=f"✅ -{cost} Points")
            else: await m.reply_text("❌ No videos!")
    else: await m.reply_text(f"❌ Need {cost} Points!")

@bot.on_message(filters.regex("📸 PHOTO"))
async def photo(c, m):
    u = await get_user(m.from_user.id)
    cost = int(await get_setting("photo_cost"))
    if u['points'] >= cost:
        async with DB_POOL.acquire() as conn:
            res = await conn.fetchrow("SELECT file_id FROM files WHERE type='photo' ORDER BY RANDOM() LIMIT 1")
            if res:
                await update_points(u['user_id'], -cost)
                await m.reply_photo(res['file_id'], caption=f"✅ -{cost} Points")
            else: await m.reply_text("❌ No photos!")
    else: await m.reply_text(f"❌ Need {cost} Points!")

# --- ADMIN PANEL LOGIC ---

@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_cmd(c, m):
    await m.reply_text("👮‍♂️ **Admin Control Panel**", reply_markup=admin_kb())

@bot.on_callback_query()
async def admin_callbacks(c, q: CallbackQuery):
    user_id = q.from_user.id
    if user_id != ADMIN_ID: return
    data = q.data

    if data == "close":
        await q.message.delete()

    elif data == "adm_stats":
        async with DB_POOL.acquire() as conn:
            u = await conn.fetchval("SELECT COUNT(*) FROM users")
            f = await conn.fetchval("SELECT COUNT(*) FROM files")
            ch = await get_setting("force_channel")
        await q.answer(f"📊 Stats:\nUsers: {u}\nFiles: {f}\nChannel: {ch}", show_alert=True)

    elif data == "adm_cast":
        await q.message.edit_text("📢 **Broadcast:** Reply to a msg with `/broadcast`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "adm_all":
        await q.message.edit_text("🎁 **Gift All:** Use `/add_all 100`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    # SET CHANNEL INSTRUCTION
    elif data == "set_ch":
        curr = await get_setting("force_channel")
        await q.message.edit_text(
            f"📢 **Set Force Channel** (Curr: {curr})\n\n"
            "Make bot admin in channel, then send:\n"
            "`/set_channel -1001234567890`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]])
        )

    elif data == "set_w":
        curr = await get_setting("welcome_bonus")
        await q.message.edit_text(f"⚙️ **Set Welcome Bonus** (Curr: {curr})\nSend: `/set_welcome 10`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "adm_add":
        await q.message.edit_text("➕ **Add User Pts**\nUse: `/add UserID Amount`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "set_v":
        curr = await get_setting("video_cost")
        await q.message.edit_text(f"⚙️ **Set Video Cost** (Curr: {curr})\nSend: `/set_video 10`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "set_p":
        curr = await get_setting("photo_cost")
        await q.message.edit_text(f"⚙️ **Set Photo Cost** (Curr: {curr})\nSend: `/set_photo 5`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "set_r":
        curr = await get_setting("referral_bonus")
        await q.message.edit_text(f"⚙️ **Set Refer Bonus** (Curr: {curr})\nSend: `/set_refer 50`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))
    
    elif data == "set_l":
        await q.message.edit_text("🔗 **Set Buy Link**\nSend: `/set_link https://..`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))
        
    elif data == "set_c":
        await q.message.edit_text("💬 **Set Contact Link**\nSend: `/set_contact https://..`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]))

    elif data == "back_admin":
        await q.message.edit_text("👮‍♂️ **Admin Control Panel**", reply_markup=admin_kb())

# --- ADMIN COMMANDS ---
@bot.on_message(filters.command("set_channel") & filters.user(ADMIN_ID))
async def set_chan(c, m):
    try: await set_setting("force_channel", m.text.split()[1]); await m.reply_text("✅ Channel Updated!")
    except: await m.reply_text("❌ Usage: `/set_channel -100xxxxxxx`")

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast(c, m):
    msg = await m.reply_text("⏳ Broadcasting...")
    n = 0
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        for r in rows:
            try:
                await m.reply_to_message.copy(r['user_id'])
                n += 1
                await asyncio.sleep(0.1)
            except: pass
    await msg.edit_text(f"✅ Sent to {n} users.")

@bot.on_message(filters.command("add_all") & filters.user(ADMIN_ID))
async def add_all(c, m):
    try:
        amt = int(m.text.split()[1])
        msg = await m.reply_text(f"⏳ Sending {amt} points to EVERYONE...")
        async with DB_POOL.acquire() as conn: await conn.execute("UPDATE users SET points = points + $1", amt)
        await msg.edit_text("✅ Done! Sabko points mil gaye.")
    except: pass

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_p(c, m):
    try: _, u, p = m.text.split(); await update_points(int(u), int(p)); await m.reply_text("✅ Added")
    except: pass

@bot.on_message(filters.command("set_refer") & filters.user(ADMIN_ID))
async def set_ref(c, m):
    try: await set_setting("referral_bonus", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_welcome") & filters.user(ADMIN_ID))
async def set_wel(c, m):
    try: await set_setting("welcome_bonus", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_video") & filters.user(ADMIN_ID))
async def set_vid(c, m):
    try: await set_setting("video_cost", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_photo") & filters.user(ADMIN_ID))
async def set_pho(c, m):
    try: await set_setting("photo_cost", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_link") & filters.user(ADMIN_ID))
async def set_lnk(c, m):
    try: await set_setting("buy_link", m.text.split()[1]); await m.reply_text("✅ Set")
    except: pass

@bot.on_message(filters.command("set_contact") & filters.user(ADMIN_ID))
async def set_con(c, m):
    try: await set_setting("contact_link", m.text.split()[1]); await m.reply_text("✅ Set")
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
