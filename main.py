import os
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# 👇 APNI DETAILS NICHE DHYAN SE BHARO 👇
# ==========================================

# 1. Telegram Details
API_ID = 28186012       # Apni API ID (Numbers me)
API_HASH = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"   # Apna API Hash (Quotes me)
BOT_TOKEN = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"  # Bot Token (Quotes me)

# 2. Database Detail (Wahi lamba wala link)
MONGO_URL = "mongodb+srv://northamericaserver075_db_user:LctsIHdZSuiZSMYd@cluster0.rclyoen.mongodb.net/?appName=Cluster0"

# 3. Channel IDs (Minus -100 jarur lagana)
CHANNEL_ID = -1003460038293   # Force Subscribe Channel
LOG_CHANNEL_ID = -1003602418876 # Jahan Video upload karoge
ADMIN_ID = 2145958203         # Apni khud ki User ID
OWNER_USERNAME = "MRPROFESSOR_00" # Bina @ ke likhna

# ==========================================

# --- MONGODB CONNECTION ---
try:
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["telegram_bot_db"]
    users_col = db["users"]
    files_col = db["files"]
    print("✅ MongoDB Connected!")
except Exception as e:
    print(f"❌ MongoDB Error: {e}")

# --- FLASK SERVER (RENDER LIVE RAKHNE KE LIYE) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running with Database!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- BOT CLIENT ---
bot = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- HELPER FUNCTIONS ---

async def is_subscribed(user_id):
    try:
        # Admin ko check karne ki zarurat nahi
        if user_id == ADMIN_ID: return True
        
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except Exception as e:
        print(f"Sub Check Error: {e}")
    return False

async def add_user(user_id, referrer_id=None):
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        new_user = {"user_id": user_id, "points": 10, "referrals": 0, "referrer": referrer_id}
        await users_col.insert_one(new_user)
        
        # Referral Logic
        if referrer_id and referrer_id != user_id:
            referrer = await users_col.find_one({"user_id": referrer_id})
            if referrer:
                await users_col.update_one({"user_id": referrer_id}, {"$inc": {"points": 20, "referrals": 1}})
                try:
                    await bot.send_message(referrer_id, "🎉 New user joined via your link! +20 Points added.")
                except:
                    pass
        return True
    return False

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 VIDEO (5 Pts)", callback_data="get_video"), InlineKeyboardButton("📸 PHOTO (2 Pts)", callback_data="get_photo")],
        [InlineKeyboardButton("🥇 POINTS", callback_data="balance"), InlineKeyboardButton("👤 PROFILE", callback_data="profile")],
        [InlineKeyboardButton("🔗 REFER & EARN", callback_data="refer"), InlineKeyboardButton("💰 BUY POINTS", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

# --- COMMAND HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    text = message.text.split()
    referrer_id = int(text[1]) if len(text) > 1 else None
    
    # Check Force Subscribe
    if not await is_subscribed(user_id):
        try:
            invite_link = await client.export_chat_invite_link(CHANNEL_ID)
        except:
            invite_link = "https://t.me/YourChannelLink" # Fallback
            
        join_btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel First", url=invite_link)]])
        await message.reply("⚠️ **You must join our channel to use this bot!**", reply_markup=join_btn)
        return

    await add_user(user_id, referrer_id)
    await message.reply(f"👋 **Welcome {message.from_user.first_name}!**\n\nEarn points by referring friends and watch premium content.", reply_markup=main_menu())

@bot.on_callback_query()
async def callback_handler(client, callback):
    user_id = callback.from_user.id
    data = callback.data
    
    if not await is_subscribed(user_id):
        await callback.answer("⚠️ Join Channel First!", show_alert=True)
        return

    user = await users_col.find_one({"user_id": user_id})
    if not user:
        await add_user(user_id)
        user = await users_col.find_one({"user_id": user_id})

    if data == "balance":
        await callback.answer(f"💰 Your Points: {user['points']}", show_alert=True)
        
    elif data == "profile":
        txt = (f"👤 **User Profile**\n\n"
               f"🆔 ID: `{user_id}`\n"
               f"💰 Points: {user['points']}\n"
               f"👥 Total Referrals: {user.get('referrals', 0)}")
        await callback.edit_message_text(txt, reply_markup=main_menu())

    elif data == "refer":
        link = f"https://t.me/{client.me.username}?start={user_id}"
        await callback.edit_message_text(f"🔗 **Referral Link:**\n`{link}`\n\nShare this link. When a friend joins, you get +20 Points!", reply_markup=main_menu())

    elif data == "get_video":
        if user['points'] >= 5:
            # Random Video Fetch
            pipeline = [{"$match": {"type": "video"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -5}})
                await client.send_video(user_id, media[0]['file_id'], caption="✅ **-5 Points Deducted**")
            else:
                await callback.answer("❌ No videos available yet! Wait for Admin upload.", show_alert=True)
        else:
            await callback.answer("❌ Low Balance! Refer friends to earn points.", show_alert=True)

    elif data == "get_photo":
        if user['points'] >= 2:
            # Random Photo Fetch
            pipeline = [{"$match": {"type": "photo"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -2}})
                await client.send_photo(user_id, media[0]['file_id'], caption="✅ **-2 Points Deducted**")
            else:
                await callback.answer("❌ No photos available yet!", show_alert=True)
        else:
            await callback.answer("❌ Low Balance!", show_alert=True)

# --- AUTO INDEXING (Admin Log Channel) ---
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def auto_index(client, message):
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.photo:
        file_id = message.photo.file_id
        file_type = "photo"
    else:
        return

    # Check duplicate
    if not await files_col.find_one({"file_id": file_id}):
        await files_col.insert_one({"file_id": file_id, "type": file_type})
        try: await message.react(emoji="🔥") # React to confirm
        except: pass

# --- ADMIN COMMANDS ---
@bot.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(client, message):
    users = await users_col.count_documents({})
    files = await files_col.count_documents({})
    await message.reply(f"📊 **Stats:**\nUsers: {users}\nFiles: {files}")

@bot.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_points(client, message):
    try:
        _, uid, pts = message.text.split()
        await users_col.update_one({"user_id": int(uid)}, {"$inc": {"points": int(pts)}})
        await message.reply(f"✅ Added {pts} points to {uid}")
    except:
        await message.reply("Usage: /add <user_id> <amount>")

# --- STARTUP ---
if __name__ == "__main__":
    print("🌍 Starting Flask Server...")
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

    print("🤖 Starting Telegram Bot...")
    bot.run()
