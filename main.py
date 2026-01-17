import logging
import random
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURATION (Ise Environment Variables se bharna best hai) ---
import os

API_ID = int(os.environ.get("API_ID", "28186012")) # Apni API ID
API_HASH = os.environ.get("API_HASH", "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://northamericaserver075_db_user:LctsIHdZSuiZSMYd@cluster0.rclyoen.mongodb.net/?appName=Cluster0")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003460038293")) # Force Sub Channel
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "-1003602418876")) # Media Storage Channel
ADMIN_ID = int(os.environ.get("ADMIN_ID", "2145958203"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "MRPROFESSOR_00")

# --- DATABASE SETUP ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["telegram_bot_db"]
users_col = db["users"]
files_col = db["files"]

# --- BOT SETUP ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER FUNCTIONS ---

async def is_subscribed(user_id):
    try:
        member = await app.get_chat_member(CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except Exception:
        pass
    return False

async def add_user(user_id, referrer_id=None):
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        new_user = {
            "user_id": user_id,
            "points": 10, # Welcome Bonus
            "referrals": 0,
            "referrer": referrer_id
        }
        await users_col.insert_one(new_user)
        
        # Referral Logic
        if referrer_id and referrer_id != user_id:
            referrer = await users_col.find_one({"user_id": referrer_id})
            if referrer:
                await users_col.update_one({"user_id": referrer_id}, {"$inc": {"points": 20, "referrals": 1}})
                try:
                    await app.send_message(referrer_id, "🎉 New user joined via your link! +20 Points added.")
                except:
                    pass
        return True
    return False

# --- KEYBOARDS ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 VIDEO (5 Pts)", callback_data="get_video"), InlineKeyboardButton("📸 PHOTO (2 Pts)", callback_data="get_photo")],
        [InlineKeyboardButton("🥇 POINTS", callback_data="balance"), InlineKeyboardButton("👤 PROFILE", callback_data="profile")],
        [InlineKeyboardButton("🔗 REFER & EARN", callback_data="refer"), InlineKeyboardButton("💰 BUY POINTS", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    text = message.text.split()
    referrer_id = int(text[1]) if len(text) > 1 else None
    
    # Check Force Sub
    if not await is_subscribed(user_id):
        join_btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel First", url="https://t.me/YourChannelLink")]])
        await message.reply("⚠️ You must join our channel to use this bot!", reply_markup=join_btn)
        return

    # Add User to DB
    await add_user(user_id, referrer_id)
    await message.reply("👋 Welcome to the Media Bot!", reply_markup=main_menu())

@app.on_callback_query()
async def callback_handler(client, callback):
    user_id = callback.from_user.id
    data = callback.data
    
    if not await is_subscribed(user_id):
        await callback.answer("⚠️ Join Channel First!", show_alert=True)
        return

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
        await callback.edit_message_text(f"🔗 **Your Referral Link:**\n`{link}`\n\nShare this to earn 20 points per user!", reply_markup=main_menu())

    elif data == "get_video":
        cost = 5
        if user['points'] >= cost:
            # Fetch Random Video
            pipeline = [{"$match": {"type": "video"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -cost}})
                await client.send_video(user_id, media[0]['file_id'], caption=f"✅ -{cost} Points")
            else:
                await callback.answer("❌ No videos found in DB!", show_alert=True)
        else:
            await callback.answer("❌ Low Balance! Refer friends.", show_alert=True)

    elif data == "get_photo":
        cost = 2
        if user['points'] >= cost:
             # Fetch Random Photo
            pipeline = [{"$match": {"type": "photo"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -cost}})
                await client.send_photo(user_id, media[0]['file_id'], caption=f"✅ -{cost} Points")
            else:
                await callback.answer("❌ No photos found in DB!", show_alert=True)
        else:
            await callback.answer("❌ Low Balance! Refer friends.", show_alert=True)

# --- AUTO INDEXING (Admin Channel) ---
@app.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def auto_index(client, message):
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.photo:
        file_id = message.photo.file_id
        file_type = "photo"
    else:
        return

    # Save to DB
    existing = await files_col.find_one({"file_id": file_id})
    if not existing:
        await files_col.insert_one({"file_id": file_id, "type": file_type})
        # Optional: React to confirm saving
        try: await message.react(emoji="🔥")
        except: pass

# --- ADMIN COMMANDS ---
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(client, message):
    users = await users_col.count_documents({})
    files = await files_col.count_documents({})
    await message.reply(f"📊 **Stats:**\nUsers: {users}\nFiles: {files}")

@app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_points(client, message):
    try:
        _, uid, pts = message.text.split()
        await users_col.update_one({"user_id": int(uid)}, {"$inc": {"points": int(pts)}})
        await message.reply(f"✅ Added {pts} points to {uid}")
    except:
        await message.reply("Usage: /add <user_id> <amount>")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast(client, message):
    all_users = users_col.find({})
    success = 0
    async for user in all_users:
        try:
            await message.reply_to_message.copy(user['user_id'])
            success += 1
            await asyncio.sleep(0.1) # Floodwait protection
        except:
            pass
    await message.reply(f"📢 Broadcast Complete. Sent to {success} users.")

print("Bot Started...")
app.run()
