import logging
import random
import asyncio
import os
from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "28186012")) # Apni API ID
API_HASH = os.environ.get("API_HASH", "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://northamericaserver075_db_user:LctsIHdZSuiZSMYd@cluster0.rclyoen.mongodb.net/?appName=Cluster0")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003460038293")) # Force Sub Channel
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "-1003602418876")) # Media Storage Channel
ADMIN_ID = int(os.environ.get("ADMIN_ID", "2145958203"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "MRPROFESSOR_00")
PORT = int(os.environ.get("PORT", 8080)) # Render ye port dega

# --- DATABASE SETUP ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["telegram_bot_db"]
users_col = db["users"]
files_col = db["files"]

# --- BOT SETUP ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (RENDER KO KHUSH RAKHNE KE LIYE) ---
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("Bot is Running Smoothly!")

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app

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
        new_user = {"user_id": user_id, "points": 10, "referrals": 0, "referrer": referrer_id}
        await users_col.insert_one(new_user)
        if referrer_id and referrer_id != user_id:
            referrer = await users_col.find_one({"user_id": referrer_id})
            if referrer:
                await users_col.update_one({"user_id": referrer_id}, {"$inc": {"points": 20, "referrals": 1}})
                try: await app.send_message(referrer_id, "🎉 New user joined! +20 Points added.")
                except: pass
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
    
    if not await is_subscribed(user_id):
        join_btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel First", url="https://t.me/YourChannelLink")]])
        await message.reply("⚠️ You must join our channel to use this bot!", reply_markup=join_btn)
        return

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
        txt = (f"👤 **User Profile**\n🆔 ID: `{user_id}`\n💰 Points: {user['points']}\n👥 Total Referrals: {user.get('referrals', 0)}")
        await callback.edit_message_text(txt, reply_markup=main_menu())
    elif data == "refer":
        link = f"https://t.me/{client.me.username}?start={user_id}"
        await callback.edit_message_text(f"🔗 **Referral Link:**\n`{link}`\n\nShare to earn 20 points!", reply_markup=main_menu())
    elif data == "get_video":
        if user['points'] >= 5:
            pipeline = [{"$match": {"type": "video"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -5}})
                await client.send_video(user_id, media[0]['file_id'], caption="✅ -5 Points")
            else: await callback.answer("❌ No videos found!", show_alert=True)
        else: await callback.answer("❌ Low Balance!", show_alert=True)
    elif data == "get_photo":
        if user['points'] >= 2:
            pipeline = [{"$match": {"type": "photo"}}, {"$sample": {"size": 1}}]
            cursor = files_col.aggregate(pipeline)
            media = await cursor.to_list(length=1)
            if media:
                await users_col.update_one({"user_id": user_id}, {"$inc": {"points": -2}})
                await client.send_photo(user_id, media[0]['file_id'], caption="✅ -2 Points")
            else: await callback.answer("❌ No photos found!", show_alert=True)
        else: await callback.answer("❌ Low Balance!", show_alert=True)

@app.on_message(filters.chat(LOG_CHANNEL_ID) & (filters.video | filters.photo))
async def auto_index(client, message):
    file_type = "video" if message.video else "photo"
    file_id = message.video.file_id if message.video else message.photo.file_id
    if not await files_col.find_one({"file_id": file_id}):
        await files_col.insert_one({"file_id": file_id, "type": file_type})
        try: await message.react(emoji="🔥")
        except: pass

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(client, message):
    u = await users_col.count_documents({})
    f = await files_col.count_documents({})
    await message.reply(f"📊 Users: {u}\nFiles: {f}")

@app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_points(client, message):
    try:
        _, uid, pts = message.text.split()
        await users_col.update_one({"user_id": int(uid)}, {"$inc": {"points": int(pts)}})
        await message.reply("✅ Done")
    except: pass

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast(client, message):
    async for user in users_col.find({}):
        try: await message.reply_to_message.copy(user['user_id'])
        except: pass
    await message.reply("📢 Sent.")

# --- STARTUP LOGIC (Modified for Render) ---
if __name__ == "__main__":
    print("Starting Bot...")
    app.start() # Start the bot client
    print("Bot Started!")
    
    # Start the Dummy Web Server
    app_runner = web.AppRunner(await web_server())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app_runner.setup())
    site = web.TCPSite(app_runner, "0.0.0.0", PORT)
    loop.run_until_complete(site.start())
    print(f"Web Server running on port {PORT}")

    # Keep the bot running
    idle()
    app.stop()
