import os
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
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
OWNER_USERNAME = "MRPROFESSOR_00"

# Welcome Photo (Optional)
WELCOME_PIC = "https://telegra.ph/file/5b97454f7675903277717.jpg"

# ==========================================

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "PostgreSQL Bot Live!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("pro_pg_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE FUNCTIONS (PostgreSQL) ---
DB_POOL = None

async def init_db():
    global DB_POOL
    try:
        # Connection Pool bana rahe hain
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        
        # Tables bana rahe hain (Users aur Files ke liye)
        async with DB_POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    name TEXT,
                    points INT DEFAULT 10,
                    referrals INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    type TEXT
                );
            """)
        print("✅ PostgreSQL Connected & Tables Ready!")
    except Exception as e:
        print(f"❌ DB Error: {e}")

async def get_user(user_id, name):
    async with DB_POOL.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not user:
            await conn.execute("INSERT INTO users (user_id, name, points, referrals) VALUES ($1, $2, 10, 0)", user_id, name)
            return {"user_id": user_id, "name": name, "points": 10, "referrals": 0}
        return user

async def update_points(user_id, points):
    async with DB_POOL.acquire() as conn:
        await conn.execute("UPDATE users SET points = points + $1 WHERE user_id = $2", points, user_id)

async def add_referral(referrer_id):
    async with DB_POOL.acquire() as conn:
        await conn.execute("UPDATE users SET points = points + 20, referrals = referrals + 1 WHERE user_id = $1", referrer_id)

async def is_joined(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        if m.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except: pass
    return False

# --- KEYBOARDS ---
def start_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Get Video", callback_data="get_video"), InlineKeyboardButton("📸 Get Photo", callback_data="get_photo")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile"), InlineKeyboardButton("💰 Points", callback_data="balance")],
        [InlineKeyboardButton("🔗 Refer & Earn", callback_data="refer"), InlineKeyboardButton("💎 Buy Points", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ Add Pts", callback_data="admin_add"), InlineKeyboardButton("➖ Cut Pts", callback_data="admin_sub")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

# --- COMMANDS ---

@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    user_id = m.from_user.id
    name = m.from_user.first_name
    
    # Initialize User
    await get_user(user_id, name)
    
    # Referral Check
    text = m.text.split()
    if len(text) > 1:
        try:
            ref_id = int(text[1])
            if ref_id != user_id:
                # Check if ref_id exists
                async with DB_POOL.acquire() as conn:
                    referrer = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", ref_id)
                    # Check if user is new (abhi abhi create hua hai upar get_user me)
                    # For simplicity, we assume referral valid if clicked first time
                    if referrer:
                        # Hum maan rahe hain ki agar user DB me pehle nahi tha to referral valid hai
                        # (Complex logic hata diya simple rakhne ke liye)
                        await add_referral(ref_id)
                        try: await c.send_message(ref_id, f"🎉 **New Referral!**\n{name} joined.\n**+20 Points** added!")
                        except: pass
        except: pass

    # Force Sub Check
    if not await is_joined(user_id):
        try: link = await c.export_chat_invite_link(CHANNEL_ID)
        except: link = "https://t.me/"
        await m.reply_text("🔒 **Access Denied!**\n\nJoin channel to use bot.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]]))
        return

    msg = f"👋 **Hello {name}!**\n\nWelcome to Premium Bot.\nEarn points & watch content."
    try: await m.reply_photo(WELCOME_PIC, caption=msg, reply_markup=start_kb(user_id))
    except: await m.reply_text(msg, reply_markup=start_kb(user_id))

# --- CALLBACKS ---

@bot.on_callback_query()
async def cb_handler(c, q: CallbackQuery):
    user_id = q.from_user.id
    data = q.data
    
    if data == "close": await q.message.delete(); return
    if not await is_joined(user_id): await q.answer("⚠️ Join Channel First!", show_alert=True); return

    user = await get_user(user_id, q.from_user.first_name)

    if data == "profile":
        txt = f"👤 **Profile**\n\n📛 Name: {user['name']}\n🆔 ID: `{user_id}`\n💰 Points: `{user['points']}`\n👥 Referrals: `{user['referrals']}`"
        try: await q.edit_message_caption(caption=txt, reply_markup=start_kb(user_id))
        except: await q.edit_message_text(txt, reply_markup=start_kb(user_id))

    elif data == "balance":
        await q.answer(f"💰 Balance: {user['points']}", show_alert=True)

    elif data == "refer":
        link = f"https://t.me/{c.me.username}?start={user_id}"
        await c.send_message(user_id, f"🔗 **Referral Link**\n\n`{link}`\n\nShare & Earn +20 Points!")
        await q.answer("Link Sent to PM!", show_alert=False)

    elif data == "get_video":
        if user['points'] >= 5:
            async with DB_POOL.acquire() as conn:
                # Random Video Fetch
                res = await conn.fetchrow("SELECT file_id FROM files WHERE type='video' ORDER BY RANDOM() LIMIT 1")
                if res:
                    await update_points(user_id, -5)
                    await c.send_video(user_id, res['file_id'], caption="✅ **-5 Points**")
                else: await q.answer("❌ No videos uploaded!", show_alert=True)
        else: await q.answer("❌ Need 5 Points!", show_alert=True)

    elif data == "get_photo":
        if user['points'] >= 2:
            async with DB_POOL.acquire() as conn:
                res = await conn.fetchrow("SELECT file_id FROM files WHERE type='photo' ORDER BY RANDOM() LIMIT 1")
                if res:
                    await update_points(user_id, -2)
                    await c.send_photo(user_id, res['file_id'], caption="✅ **-2 Points**")
                else: await q.answer("❌ No photos uploaded!", show_alert=True)
        else: await q.answer("❌ Need 2 Points!", show_alert=True)

    # --- ADMIN ---
    elif data == "admin_stats":
        if user_id != ADMIN_ID: return
        async with DB_POOL.acquire() as conn:
            u = await conn.fetchval("SELECT COUNT(*) FROM users")
            f = await conn.fetchval("SELECT COUNT(*) FROM files")
            await q.answer(f"📊 Users: {u} | Files: {f}", show_alert=True)

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID: return
        await c.send_message(user_id, "📢 Reply to a message with `/broadcast`")

    elif data == "admin_add":
        if user_id != ADMIN_ID: return
        await c.send_message(user_id, "ℹ️ Use: `/add 123456789 100`")

# --- ADMIN COMMANDS ---
@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(c, m): await m.reply_text("👮‍♂️ **Admin Panel**", reply_markup=admin_kb())

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
async def add_pts(c, m):
    try:
        _, uid, pts = m.text.split()
        await update_points(int(uid), int(pts))
        await m.reply_text(f"✅ Added {pts} pts to {uid}")
    except: pass

@bot.on_message(filters.command("deduct") & filters.user(ADMIN_ID))
async def sub_pts(c, m):
    try:
        _, uid, pts = m.text.split()
        await update_points(int(uid), -int(pts))
        await m.reply_text(f"✅ Deducted {pts} pts from {uid}")
    except: pass

# --- AUTO INDEXING ---
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def index_media(c, m):
    try:
        if m.video: fid, ftype = m.video.file_id, "video"
        elif m.photo: fid, ftype = m.photo.file_id, "photo"
        else: return
        
        async with DB_POOL.acquire() as conn:
            # Postgres me "ON CONFLICT DO NOTHING" duplicates handle karta hai
            await conn.execute("INSERT INTO files (file_id, type) VALUES ($1, $2) ON CONFLICT (file_id) DO NOTHING", fid, ftype)
            await m.react(emoji="🔥")
    except: pass

# --- STARTUP ---
if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    
    # Initialize DB before Bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    
    print("🚀 Postgres Bot Started!")
    bot.run()
