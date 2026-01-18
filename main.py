import os
import json
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# 👇 BAS YAHAN APNI DETAILS BHARO 👇
# ==========================================

API_ID = 28186012       # Apni API ID (Number)
API_HASH = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"   # API Hash (Quotes me)
BOT_TOKEN = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"  # Bot Token (Quotes me)

# Channel IDs (-100 jarur lagana)
CHANNEL_ID = -1003460038293   # Force Subscribe Channel
LOG_CHANNEL_ID = -1003602418876 # Video Upload Channel
ADMIN_ID = 2145958203       # Teri User ID
OWNER_USERNAME = "MRPROFESSOR_00" # Bina @ ke

# ==========================================

# --- LOCAL DATABASE SYSTEM (NO MONGODB) ---
DB_FILE = "database.json"
DATA = {"users": {}, "files": []}

def load_db():
    global DATA
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            DATA = json.load(f)

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(DATA, f)

# Load data on start
load_db()

# --- FLASK SERVER (RENDER KE LIYE) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running on Local DB!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- BOT CLIENT ---
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER FUNCTIONS ---

async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except:
        pass
    return False

def get_user(user_id):
    uid = str(user_id)
    if uid not in DATA["users"]:
        DATA["users"][uid] = {"points": 10, "referrals": 0} # Welcome Bonus
        save_db()
    return DATA["users"][uid]

def update_points(user_id, points):
    uid = str(user_id)
    if uid in DATA["users"]:
        DATA["users"][uid]["points"] += points
        save_db()

# --- KEYBOARD ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 VIDEO (5 Pts)", callback_data="get_video"), InlineKeyboardButton("📸 PHOTO (2 Pts)", callback_data="get_photo")],
        [InlineKeyboardButton("🥇 POINTS", callback_data="balance"), InlineKeyboardButton("👤 PROFILE", callback_data="profile")],
        [InlineKeyboardButton("🔗 REFER", callback_data="refer"), InlineKeyboardButton("💰 BUY", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    uid = str(user_id)
    text = message.text.split()
    
    # Check Force Sub
    if not await is_subscribed(user_id):
        try: invite = await client.export_chat_invite_link(CHANNEL_ID)
        except: invite = "https://t.me/"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel First", url=invite)]])
        await message.reply("⚠️ **Join Channel First!**", reply_markup=btn)
        return

    # Add User / Referral
    if uid not in DATA["users"]:
        DATA["users"][uid] = {"points": 10, "referrals": 0}
        # Referral Logic
        if len(text) > 1:
            try:
                ref_id = text[1]
                if ref_id != uid and ref_id in DATA["users"]:
                    update_points(ref_id, 20)
                    DATA["users"][ref_id]["referrals"] += 1
                    save_db()
                    await client.send_message(int(ref_id), "🎉 New Referral! +20 Points.")
            except: pass
        save_db()

    await message.reply("👋 **Welcome!**", reply_markup=main_menu())

@bot.on_callback_query()
async def callback_handler(client, callback):
    user_id = callback.from_user.id
    uid = str(user_id)
    data = callback.data
    
    if not await is_subscribed(user_id):
        await callback.answer("⚠️ Join Channel First!", show_alert=True)
        return

    user = get_user(user_id)

    if data == "balance":
        await callback.answer(f"💰 Points: {user['points']}", show_alert=True)

    elif data == "profile":
        txt = f"👤 **Profile**\n🆔: `{user_id}`\n💰 Points: {user['points']}\n👥 Referrals: {user['referrals']}"
        await callback.edit_message_text(txt, reply_markup=main_menu())

    elif data == "refer":
        link = f"https://t.me/{client.me.username}?start={user_id}"
        await callback.edit_message_text(f"🔗 **Link:**\n`{link}`\n\nShare to earn 20 Pts!", reply_markup=main_menu())

    elif data == "get_video":
        if user['points'] >= 5:
            videos = [f for f in DATA["files"] if f["type"] == "video"]
            if videos:
                import random
                media = random.choice(videos)
                update_points(user_id, -5)
                await client.send_video(user_id, media["id"], caption="✅ -5 Pts")
            else:
                await callback.answer("❌ No videos yet!", show_alert=True)
        else:
            await callback.answer("❌ Need 5 Points!", show_alert=True)

    elif data == "get_photo":
        if user['points'] >= 2:
            photos = [f for f in DATA["files"] if f["type"] == "photo"]
            if photos:
                import random
                media = random.choice(photos)
                update_points(user_id, -2)
                await client.send_photo(user_id, media["id"], caption="✅ -2 Pts")
            else:
                await callback.answer("❌ No photos yet!", show_alert=True)
        else:
            await callback.answer("❌ Need 2 Points!", show_alert=True)

# --- AUTO INDEXING ---
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def auto_index(client, message):
    try:
        if message.video:
            fid = message.video.file_id
            ftype = "video"
        elif message.photo:
            fid = message.photo.file_id
            ftype = "photo"
        else: return

        # Check Duplicate
        exists = any(f["id"] == fid for f in DATA["files"])
        if not exists:
            DATA["files"].append({"id": fid, "type": ftype})
            save_db()
            await message.react(emoji="🔥")
    except Exception as e:
        print(f"Index Error: {e}")

# --- ADMIN ---
@bot.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(client, message):
    u = len(DATA["users"])
    f = len(DATA["files"])
    await message.reply(f"📊 Users: {u}\nFiles: {f}")

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_pts(client, message):
    try:
        _, uid, pts = message.text.split()
        update_points(uid, int(pts))
        await message.reply("✅ Done")
    except: pass

# --- START ---
if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    print("Bot Starting...")
    bot.run()
