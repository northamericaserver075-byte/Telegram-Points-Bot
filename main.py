import os
import threading
from flask import Flask
from pyrogram import Client, filters

# ==========================================
# 👇 APNI DETAILS NICHE BRACKET KE ANDAR LIKHO 👇
# ==========================================

api_id = 28186012  # Yahan apni API ID numbers me likho
api_hash = "ecbdbf51d3c6cdcf9a39ac1e7b1d79b6"
bot_token = "8394919663:AAHZzRgdimPxn-O7PTnNAFgzqkhRoV0ZGiI"

# ==========================================

# --- FLASK SERVER (Render ko zinda rakhne ke liye) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Successfully!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- TELEGRAM BOT ---
bot = Client(
    "my_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply(f"🎉 **MUBARAK HO!**\n\nBot chal gaya hai bhai.\nCode sahi hai, Token sahi hai.")

# --- STARTUP LOGIC ---
if __name__ == "__main__":
    print("Starting Web Server...")
    # Flask ko alag thread me chalayenge
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

    print("Starting Telegram Bot...")
    bot.run()
