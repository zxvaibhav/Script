import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid, ChatAdminRequired
import yt_dlp
import requests
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
API_ID = int(os.getenv("API_ID", "32819831"))
API_HASH = os.getenv("API_HASH", "78c8247d43646a5cfb7199f54cd25ffc")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7798631552:AAF0hhd1jJccWOa0hIUh-yZfweVu0EaxsQg")

# Initialize Pyrogram client
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store for user sessions and music queues
user_sessions = {}
music_queues = {}

class MusicPlayer:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.queue = []
        self.is_playing = False
        self.current_song = None

    def add_to_queue(self, song_info):
        """Add song to the queue"""
        self.queue.append(song_info)
        return len(self.queue)

    def get_next_song(self):
        """Get next song from queue"""
        if self.queue:
            self.current_song = self.queue.pop(0)
            return self.current_song
        self.current_song = None
        return None

    def clear_queue(self):
        """Clear the music queue"""
        self.queue.clear()
        self.current_song = None
        self.is_playing = False

def get_music_player(chat_id):
    """Get or create music player for chat"""
    if chat_id not in music_queues:
        music_queues[chat_id] = MusicPlayer(chat_id)
    return music_queues[chat_id]

def search_youtube(query):
    """Search YouTube for music"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info and info['entries']:
                return info['entries'][0]
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return None

def get_audio_url(video_info):
    """Get direct audio URL from video info"""
    try:
        formats = video_info.get('formats', [])
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        if audio_formats:
            # Prefer opus format for better quality
            opus_format = next((f for f in audio_formats if f.get('ext') == 'webm'), None)
            if opus_format:
                return opus_format['url']
            
            # Fallback to any audio format
            return audio_formats[0]['url']
        
        # If no audio-only format, get best format with audio
        for fmt in formats:
            if fmt.get('acodec') != 'none':
                return fmt['url']
                
        return None
    except Exception as e:
        logger.error(f"Error getting audio URL: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handle /start command"""
    await message.reply_text(
        "🎵 **Music Bot Started!**\n\n"
        "Available commands:\n"
        "• `/play <song name>` - Play music\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop music\n"
        "• `/queue` - Show current queue\n"
        "• `/help` - Show this help message"
    )

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Handle /help command"""
    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "**Commands:**\n"
        "• `/play <song name>` - Search and play music\n"
        "• `/skip` - Skip to next song in queue\n"
        "• `/stop` - Stop music and clear queue\n"
        "• `/queue` - Show current music queue\n"
        "• `/help` - Show this help message\n\n"
        "**Usage:**\n"
        "Just use `/play` followed by the song name or artist!"
    )

@app.on_message(filters.command("play"))
async def play_music(client, message: Message):
    """Handle /play command"""
    try:
        # Check if user provided song name
        if len(message.command) < 2:
            await message.reply_text("❌ Please provide a song name. Usage: `/play <song name>`")
            return

        # Extract song query
        query = " ".join(message.command[1:])
        chat_id = message.chat.id
        
        await message.reply_text(f"🔍 Searching for: `{query}`...")

        # Search for the song
        video_info = search_youtube(query)
        if not video_info:
            await message.reply_text("❌ No results found. Try a different search term.")
            return

        # Get music player for this chat
        player = get_music_player(chat_id)
        
        # Prepare song info
        song_info = {
            'title': video_info.get('title', 'Unknown Title'),
            'duration': video_info.get('duration', 0),
            'url': get_audio_url(video_info),
            'thumbnail': video_info.get('thumbnail'),
            'requested_by': message.from_user.first_name if message.from_user else "Unknown"
        }

        if not song_info['url']:
            await message.reply_text("❌ Could not get audio stream. Try another song.")
            return

        # Add to queue
        position = player.add_to_queue(song_info)
        
        # Send success message
        duration = f"{song_info['duration']//60}:{song_info['duration']%60:02d}" if song_info['duration'] else "Unknown"
        
        response_text = (
            f"🎵 **Added to Queue**\n\n"
            f"**Title:** {song_info['title']}\n"
            f"**Duration:** {duration}\n"
            f"**Requested by:** {song_info['requested_by']}\n"
            f"**Position in queue:** #{position}"
        )
        
        # Send thumbnail if available
        if song_info['thumbnail']:
            try:
                await message.reply_photo(
                    photo=song_info['thumbnail'],
                    caption=response_text
                )
                return
            except Exception:
                pass  # Fallback to text only
        
        await message.reply_text(response_text)
        
        # Start playing if not already playing
        if not player.is_playing:
            await play_next_song(client, chat_id)

    except Exception as e:
        logger.error(f"Error in play_music: {e}")
        await message.reply_text("❌ An error occurred while processing your request.")

async def play_next_song(client, chat_id):
    """Play the next song in queue"""
    player = get_music_player(chat_id)
    
    if player.is_playing:
        return
        
    next_song = player.get_next_song()
    if not next_song:
        player.is_playing = False
        return
    
    player.is_playing = True
    
    try:
        # Send now playing message
        duration = f"{next_song['duration']//60}:{next_song['duration']%60:02d}" if next_song['duration'] else "Unknown"
        
        now_playing_text = (
            f"🎶 **Now Playing**\n\n"
            f"**Title:** {next_song['title']}\n"
            f"**Duration:** {duration}\n"
            f"**Requested by:** {next_song['requested_by']}"
        )
        
        # Try to send with thumbnail
        try:
            if next_song['thumbnail']:
                await client.send_photo(
                    chat_id=chat_id,
                    photo=next_song['thumbnail'],
                    caption=now_playing_text
                )
            else:
                await client.send_message(chat_id, now_playing_text)
        except Exception:
            await client.send_message(chat_id, now_playing_text)
        
        # Simulate playing (in a real bot, you'd stream audio here)
        # Note: Actual audio streaming requires voice chat implementation
        if next_song['duration']:
            await asyncio.sleep(min(next_song['duration'], 30))  # Simulate playback
        
        # Play next song
        player.is_playing = False
        await play_next_song(client, chat_id)
        
    except Exception as e:
        logger.error(f"Error playing next song: {e}")
        player.is_playing = False
        await client.send_message(chat_id, "❌ Error playing song. Moving to next...")
        await play_next_song(client, chat_id)

@app.on_message(filters.command("skip"))
async def skip_song(client, message: Message):
    """Handle /skip command"""
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    if not player.is_playing and not player.queue:
        await message.reply_text("❌ No music is currently playing.")
        return
    
    player.is_playing = False
    await message.reply_text("⏭️ Skipped current song.")
    await play_next_song(client, chat_id)

@app.on_message(filters.command("stop"))
async def stop_music(client, message: Message):
    """Handle /stop command"""
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    player.clear_queue()
    await message.reply_text("⏹️ Music stopped and queue cleared.")

@app.on_message(filters.command("queue"))
async def show_queue(client, message: Message):
    """Handle /queue command"""
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    if not player.queue and not player.current_song:
        await message.reply_text("📭 Queue is empty.")
        return
    
    queue_text = "🎵 **Music Queue**\n\n"
    
    if player.current_song:
        queue_text += f"**Now Playing:** {player.current_song['title']}\n\n"
    
    if player.queue:
        queue_text += "**Up Next:**\n"
        for i, song in enumerate(player.queue[:10], 1):  # Show first 10 songs
            duration = f"{song['duration']//60}:{song['duration']%60:02d}" if song['duration'] else "Unknown"
            queue_text += f"{i}. {song['title']} ({duration})\n"
        
        if len(player.queue) > 10:
            queue_text += f"\n...and {len(player.queue) - 10} more songs"
    else:
        queue_text += "No songs in queue"
    
    await message.reply_text(queue_text)

@app.on_message(filters.command("clear"))
async def clear_queue(client, message: Message):
    """Handle /clear command"""
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    queue_count = len(player.queue)
    player.queue.clear()
    
    await message.reply_text(f"🧹 Cleared {queue_count} songs from queue.")

if __name__ == "__main__":
    logger.info("Starting Music Bot...")
    print("🎵 Music Bot is starting...")
    print("Press Ctrl+C to stop the bot")
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")