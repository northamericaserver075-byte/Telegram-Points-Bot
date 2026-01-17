import logging
import random
import asyncio
import os
from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- LOGGING ON KARO ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "123456")) 
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")
MONGO_URL = os.environ.get("MONGO_URL", "your_mongo_url")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-100xxxx")) 
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "-100xxxx")) 
ADMIN_ID = int(os.environ.get("ADMIN_ID", "12345"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "YourUser")
PORT = int(os.environ.get("PORT", 8080)) 

# --- DATABASE SETUP ---
print("Connecting to MongoDB...")
try:
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["telegram_bot_db"]
    users_col = db["users"]
    files_col = db["files"]
    print("MongoDB Connected Successfully!")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

# --- BOT SETUP ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
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
    except Exception as e:
        print(f"Error checking subscription: {e}") # Log error
    return False

async def add_user(user_id, referrer_id=None):
    try:
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
    except Exception as e:
        print(f"Database Error in add_user: {e}")
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
    print(f"Start command received from {message.from_user.id}") # LOG
    user_id = message.from_user.id
    text = message.text.split()
    referrer_id = int(text[1]) if len(text) > 1 else None
    
    if not await is_subscribed(user_id):
        print("User not subscribed") # LOG
        join_btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel First", url="https://t.me/YourChannelLink")]])
        await message.reply("⚠️ You must join our channel to use this bot!", reply_markup=join_btn)
        return

    print("User subscribed, adding to DB...") # LOG
    await add_user(user_id, referrer_id)
    await message.reply("👋 Welcome to the Media Bot!", reply_markup=main_menu())

# ... (Baki code same rahega, bas start me logging jaruri hai) ...
# Is code ko run karke Render ke LOGS check karna.

# --- STARTUP LOGIC ---
async def start_services():
    print("Starting Bot Client...")
    await app.start()
    print("Bot Client Started! Checking bot info...")
    me = await app.get_me()
    print(f"Bot Started as @{me.username}")

    print("Starting Web Server...")
    app_runner = web.AppRunner(await web_server())
    await app_runner.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app_runner, bind_address, PORT).start()
    print(f"Web Server Running on Port {PORT}")

    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_services())
