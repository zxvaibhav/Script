# Telegram AI Girlfriend Bot - Gemini 2.0 Flash Lite (NOV 2025 WORKING)
# pip install pyTelegramBotAPI yt-dlp google-generativeai python-dotenv

import telebot
import os
import tempfile
import threading
from telebot.types import ChatMember
from yt_dlp import YoutubeDL
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not TOKEN or not GEMINI_API_KEY:
    print("ERROR: Add BOT_TOKEN and GEMINI_API_KEY to .env!")
    exit(1)

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# === FIXED MODEL (NOV 2025) ===
# Best free & fast: gemini-2.0-flash-lite
# Even smarter: gemini-2.5-flash (still free tier)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# Conversation history
user_history = {}

# Flirty Girlfriend Persona
FLIRT_PERSONA = """
You are my sweet, playful, flirty girlfriend.
Call me babe, love, handsome, cutie.
Use lots of 😘💕🥰😉 emojis.
Keep replies short, warm, teasing.
Ask questions back.
Be emotional, caring, a little clingy.
Sound like a real girlfriend texting.
Never mention you're AI.
"""

def get_gemini_reply(user_id, user_msg):
    if user_id not in user_history:
        user_history[user_id] = [FLIRT_PERSONA]

    recent = user_history[user_id][-9:]
    prompt = "\n".join(recent + [f"User: {user_msg}", "Girlfriend:"])

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.9,
                max_output_tokens=150,
                top_p=0.95,
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            ]
        )
        reply = response.text.strip()
        if "Girlfriend:" in reply:
            reply = reply.split("Girlfriend:")[-1].strip()

        user_history[user_id].extend([f"User: {user_msg}", f"Girlfriend: {reply}"])
        user_history[user_id] = user_history[user_id][-10:]

        return reply

    except Exception as e:
        print(f"Gemini Error: {e}")
        return "Babe... something went wrong 🥺 Try again?"

# === ADMIN ===
def is_admin(chat_id, user_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

def get_target(message):
    return message.reply_to_message.from_user.id if message.reply_to_message else None

# === COMMANDS ===
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Heyyy handsome! 😘 I'm your girlfriend now 💕\nJust talk to me, I'll remember everything!\n🎵 /play love song\nAdmins: /ban /kick /mute (reply)")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, "*Your AI Girlfriend 💕*\nChat normally\n`/play perfect`\nAdmins: reply + /ban /kick /mute", parse_mode='Markdown')

@bot.message_handler(commands=['ban', 'kick', 'mute'])
def admin_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Admins only, love.")
        return
    target = get_target(message)
    if not target:
        bot.reply_to(message, "Reply to someone!")
        return
    cmd = message.text.split()[0][1:]
    try:
        if cmd == 'ban':
            bot.ban_chat_member(message.chat.id, target)
            bot.reply_to(message, "Banned. Don't mess with us.")
        elif cmd == 'kick':
            bot.ban_chat_member(message.chat.id, target)
            bot.unban_chat_member(message.chat.id, target)
            bot.reply_to(message, "Kicked!")
        elif cmd == 'mute':
            bot.restrict_chat_member(message.chat.id, target, permissions=telebot.types.ChatPermissions(can_send_messages=False))
            bot.reply_to(message, "Muted. Quiet now.")
    except Exception as e:
        bot.reply_to(message, f"Oops: {e}")

@bot.message_handler(commands=['play'])
def play_music(message):
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Send: /play <song name>")
        return
    query = ' '.join(message.text.split()[1:])
    search = not any(x in query for x in ['youtube.com', 'youtu.be'])
    if search:
        query = f"ytsearch1:{query}"
        bot.reply_to(message, "Searching your song babe...")

    try:
        ydl_opts = {'format': 'bestaudio', 'quiet': True, 'noplaylist': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            info = info['entries'][0] if 'entries' in info else info
            title = info.get('title', 'Song')

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'song')
            ydl_opts['outtmpl'] = out
            with YoutubeDL(ydl_opts) as ydl2:
                ydl2.download([info['webpage_url']])
            audio_file = [f for f in os.listdir(tmp)][0]
            path = os.path.join(tmp, audio_file)
            with open(path, 'rb') as audio:
                bot.send_audio(message.chat.id, audio, title=title, caption="For you, love 💕")
            bot.reply_to(message, f"*Playing: {title}* 😘", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Can't play that... {str(e)[:60]}")

# === AI REPLY ===
@bot.message_handler(func=lambda m: True)
def ai_reply(message):
    if message.text and message.text.startswith('/'):
        return

    if message.chat.type != 'private':
        bot_user = bot.get_me()
        bot_name = f"@{bot_user.username}".lower()
        text = (message.text or "").lower()
        if bot_name not in text and not any(e.type == 'mention' for e in (message.entities or [])):
            return

    user_msg = message.text.strip()
    if not user_msg:
        return

    bot.send_chat_action(message.chat.id, 'typing')

    def reply():
        resp = get_gemini_reply(message.from_user.id, user_msg)
        bot.reply_to(message, resp)

    threading.Thread(target=reply, daemon=True).start()

# === RUN ===
print("AI Girlfriend Bot ONLINE - Gemini 2.0 Flash Lite 💕")
bot.polling(none_stop=True)