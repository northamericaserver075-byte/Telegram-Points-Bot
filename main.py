import os
import threading
import asyncio
import time
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import FloodWait
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# 👇 PRO CONFIGURATION (APNI DETAILS BHARO) 👇
# ==========================================

API_ID = 28186012       # API ID (Number)
API_HASH = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"   # API Hash (Quotes me)
BOT_TOKEN = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"  # Bot Token

# MongoDB URL (Sahi wala)
MONGO_URL = "mongodb+srv://northamericaserver075_db_user:LctsIHdZSuiZSMYd@cluster0.rclyoen.mongodb.net/?appName=Cluster0"

# Channels (-100 jarur lagana)
CHANNEL_ID = -1003460038293   # Force Subscribe Channel
LOG_CHANNEL_ID = -1003602418876 # Media Channel
ADMIN_ID = 2145958203       # Apni ID (Number)
OWNER_USERNAME = "MRPROFESSOR_00" # Bina @ ke

# Welcome Photo (Direct Link ya File ID)
WELCOME_PIC = "https://telegra.ph/file/pico_url.jpg" # Yahan koi bhi image link daal sakte ho

# ==========================================

# --- DATABASE CONNECTION ---
try:
    mongo = AsyncIOMotorClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    db = mongo["pro_bot_db"]
    users_col = db["users"]
    files_col = db["files"]
    print("✅ PRO Database Connected!")
except Exception as e:
    print(f"❌ DB Error: {e}")

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "Pro Bot Live"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("pro_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER FUNCTIONS ---

async def get_user_data(user_id):
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        new_user = {"user_id": user_id, "name": "Unknown", "points": 10, "referrals": 0}
        await users_col.insert_one(new_user)
        return new_user
    return user

async def is_joined(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        if m.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except: pass
    return False

# --- KEYBOARDS (PREMIUM LOOK) ---
def start_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Get Random Video", callback_data="get_video"), InlineKeyboardButton("📸 Get Random Photo", callback_data="get_photo")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"), InlineKeyboardButton("💰 Check Points", callback_data="balance")],
        [InlineKeyboardButton("🔗 Refer & Earn", callback_data="refer"), InlineKeyboardButton("💎 Buy Points", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ Add Points", callback_data="admin_add"), InlineKeyboardButton("➖ Deduct Points", callback_data="admin_sub")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="close")]
    ])

# --- USER COMMANDS ---

@bot.on_message(filters.command("start"))
async def start(c, m: Message):
    user_id = m.from_user.id
    name = m.from_user.first_name
    
    # Update Name in DB
    await users_col.update_one({"user_id": user_id}, {"$set": {"name": name}}, upsert=True)
    
    # Referral Check
    text = m.text.split()
    if len(text) > 1:
        ref_id = int(text[1])
        if ref_id != user_id:
            ref_user = await users_col.find_one({"user_id": ref_id})
            curr_user = await users_col.find_one({"user_id": user_id})
            if ref_user and not curr_user: # Only if new user
                await users_col.update_one({"user_id": ref_id}, {"$inc": {"points": 20, "referrals": 1}})
                await c.send_message(ref_id, f"🎉 **New Referral!**\n{name} joined using your link.\n**+20 Points** added!")

    # Force Sub Check
    if not await is_joined(user_id):
        try: link = await c.export_chat_invite_link(CHANNEL_ID)
        except: link = "https://t.me/"
        await m.reply_text(
            "🔒 **Access Denied!**\n\nYou must join our channel to use this bot.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 JOIN CHANNEL", url=link)]])
        )
        return

    # Welcome Message
    msg = f"👋 **Hello {name}!**\n\nWelcome to the **Premium Media Bot**.\nEarn points by referring friends and unlock exclusive content.\n\n👇 **Choose an option below:**"
    # Agar WELCOME_PIC valid hai to photo bhejo, nahi to text
    try: await m.reply_photo(WELCOME_PIC, caption=msg, reply_markup=start_kb(user_id))
    except: await m.reply_text(msg, reply_markup=start_kb(user_id))

# --- CALLBACK HANDLERS (BUTTONS) ---

@bot.on_callback_query()
async def cb_handler(c, q: CallbackQuery):
    user_id = q.from_user.id
    data = q.data
    
    if data == "close":
        await q.message.delete()
        return

    # Force Sub Check for Buttons
    if not await is_joined(user_id):
        await q.answer("⚠️ Join Channel First!", show_alert=True)
        return

    user = await get_user_data(user_id)

    # --- USER FEATURES ---
    if data == "profile":
        # EXACT FORMAT YOU WANTED
        txt = (
            f"👤 **User Profile**\n\n"
            f"📛 **Name:** {q.from_user.first_name}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"💰 **Points:** `{user['points']}`\n"
            f"👥 **Total Referrals:** `{user['referrals']}`"
        )
        await q.edit_message_caption(caption=txt, reply_markup=start_kb(user_id)) if q.message.photo else await q.edit_message_text(txt, reply_markup=start_kb(user_id))

    elif data == "balance":
        await q.answer(f"💰 Available Points: {user['points']}", show_alert=True)

    elif data == "refer":
        link = f"https://t.me/{c.me.username}?start={user_id}"
        await q.edit_message_caption(f"🔗 **Your Referral Link**\n\n`{link}`\n\nShare this link! When a friend joins, you get **+20 Points**.", reply_markup=start_kb(user_id)) if q.message.photo else await q.edit_message_text(f"🔗 **Your Referral Link**\n\n`{link}`\n\nShare this link! When a friend joins, you get **+20 Points**.", reply_markup=start_kb(user_id))

    elif data == "get_video":
        if user['points'] >= 5:
            pipeline = [{"$match": {"type": "video"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -5}})
                await c.send_video(user_id, media[0]['file_id'], caption="✅ **-5 Points Deducted**")
            else: await q.answer("❌ No videos in database!", show_alert=True)
        else: await q.answer("❌ Not enough points! Refer friends.", show_alert=True)

    elif data == "get_photo":
        if user['points'] >= 2:
            pipeline = [{"$match": {"type": "photo"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -2}})
                await c.send_photo(user_id, media[0]['file_id'], caption="✅ **-2 Points Deducted**")
            else: await q.answer("❌ No photos in database!", show_alert=True)
        else: await q.answer("❌ Not enough points!", show_alert=True)

    # --- ADMIN FEATURES ---
    elif data == "admin_stats":
        if user_id != ADMIN_ID: return
        u = await users_col.count_documents({})
        f = await files_col.count_documents({})
        await q.answer(f"📊 Stats:\nUsers: {u}\nFiles: {f}", show_alert=True)

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID: return
        await q.edit_message_text("📢 **Broadcast Mode**\n\nReply to any message with `/broadcast` to send it to all users.", reply_markup=admin_kb())

    elif data == "admin_add":
        if user_id != ADMIN_ID: return
        await q.answer("Use command: /add <userid> <points>", show_alert=True)

# --- ADMIN COMMANDS (IMPROVED) ---

@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(c, m):
    await m.reply_text("👮‍♂️ **Admin Control Panel**", reply_markup=admin_kb())

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast_msg(c, m):
    msg = await m.reply_text("⏳ **Broadcasting started...**")
    count = 0
    errors = 0
    async for user in users_col.find({}, {"user_id": 1}):
        try:
            await m.reply_to_message.copy(user['user_id'])
            count += 1
            await asyncio.sleep(0.1) # Prevent FloodWait
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except:
            errors += 1
    await msg.edit_text(f"✅ **Broadcast Complete!**\n\nSent to: {count}\nFailed: {errors}")

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_points_cmd(c, m):
    try:
        _, uid, pts = m.text.split()
        await users_col.update_one({"user_id": int(uid)}, {"$inc": {"points": int(pts)}})
        await m.reply_text(f"✅ Added {pts} points to User {uid}")
    except:
        await m.reply_text("❌ Usage: `/add 123456789 50`")

@bot.on_message(filters.command("deduct") & filters.user(ADMIN_ID))
async def deduct_points_cmd(c, m):
    try:
        _, uid, pts = m.text.split()
        await users_col.update_one({"user_id": int(uid)}, {"$inc": {"points": -int(pts)}})
        await m.reply_text(f"✅ Deducted {pts} points from User {uid}")
    except:
        await m.reply_text("❌ Usage: `/deduct 123456789 50`")

# --- AUTO INDEXING ---
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def index_media(c, m):
    try:
        fid = m.video.file_id if m.video else m.photo.file_id
        ftype = "video" if m.video else "photo"
        if not await files_col.find_one({"file_id": fid}):
            await files_col.insert_one({"file_id": fid, "type": ftype})
            await m.react(emoji="🔥")
    except: pass

# --- STARTUP ---
if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    print("🚀 Bot Started...")
    bot.run()
