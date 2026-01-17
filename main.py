import os
import asyncio
from pyrogram import Client, filters, idle
from aiohttp import web

# --- VARIABLES ---
# Agar yahan error aaya to matlab tumne Environment Variables galat bhare hain
API_ID = int(os.environ.get("28186012"))
API_HASH = os.environ.get("ecbdbf51d3c6cdcf9a39ac1e7b1d79b6")
BOT_TOKEN = os.environ.get("8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI")
PORT = int(os.environ.get("PORT", 8080))

# --- BOT SETUP ---
app = Client("my_test_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (Render ko zinda rakhne ke liye) ---
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("Bot is ALIVE!")

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app

# --- COMMAND ---
@app.on_message(filters.command("start"))
async def start(client, message):
    print(f"Got command from {message.from_user.first_name}")
    await message.reply("✅ **Bhai Bot Chal Gaya!**\n\nAb confirm ho gaya ki Token sahi hai. Dikkat Database me thi.")

# --- STARTUP ---
async def start_services():
    print("🤖 Starting Bot...")
    await app.start()
    me = await app.get_me()
    print(f"✅ Bot Started as @{me.username}")

    print("🌍 Starting Web Server...")
    app_runner = web.AppRunner(await web_server())
    await app_runner.setup()
    await web.TCPSite(app_runner, "0.0.0.0", PORT).start()
    print(f"✅ Web Server running on Port {PORT}")

    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_services())
