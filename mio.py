import os
import requests
import tempfile
from gtts import gTTS
from PIL import Image
import discord
from discord.ext import commands, tasks
import youtube_dl
import asyncio
import random
import json
import re

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

DISCORD_TOKEN = "dc"
OPENROUTER_API_KEY = "op"
GROQ_MODEL = "meta-llama/llama-3-8b-instruct"
HUGGINGFACE_TOKEN = "hu"
DEFAULT_PHOTO_DIR = r"C:\\Users\\alone\\OneDrive\\Desktop\\mio\\profile der"
NSFW_PHOTO_DIR = r"C:\\Users\\alone\\OneDrive\\Desktop\\mio\\photo"
LOVE_DB_PATH = r"C:\\Users\\alone\\OneDrive\\Desktop\\mio\\detabase\\love_data.json"

nsfw_mode = {}
voice_mode = {}
romantic_mode = {}
love_percent = {}
memory_data = {}

if os.path.exists(LOVE_DB_PATH):
    with open(LOVE_DB_PATH, 'r') as f:
        love_percent = json.load(f)

def save_love_data():
    with open(LOVE_DB_PATH, 'w') as f:
        json.dump(love_percent, f)

def ensure_test_photo(photo_path: str):
    if not os.path.exists(photo_path):
        os.makedirs(os.path.dirname(photo_path), exist_ok=True)
        img = Image.new('RGB', (300, 300), color='white')
        img.save(photo_path, "JPEG")

def text_to_voice(text: str) -> str or None:
    try:
        tts = gTTS(text=text, lang='hi')
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_file.name)
        return temp_file.name
    except Exception as e:
        print(f"TTS error: {e}")
        return None

def generate_image(prompt: str) -> str or None:
    try:
        res = requests.post(
            "https://api-inference.huggingface.co/models/prompthero/openjourney",
            headers={"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"},
            json={"inputs": prompt}
        )
        if res.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file.write(res.content)
            temp_file.close()
            return temp_file.name
        else:
            print(f"Image gen error: {res.text}")
            return None
    except Exception as e:
        print(f"Image exception: {e}")
        return None

def chat_with_groq(message: str, memory: str, user_id: str) -> str:
    nsfw = nsfw_mode.get(user_id, False)
    romantic = romantic_mode.get(user_id, False)
    base_prompt = "You are Mio, an anime waifu in Hinglish."
    if romantic:
        base_prompt += " You are romantic and teasing."
    if nsfw:
        base_prompt += " Add some light NSFW flirtiness."
    else:
        base_prompt += " Keep it cute and clean."
    prompt = f"{base_prompt}\nPrevious: {memory}\nUser: {message}\nMio:"
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9
            }
        )
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq error: {e}")
        return "💔 Sorry, reply generate nahi hua."

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    content = message.content.lower()

    if any(word in content for word in ["bhai", "bro"]):
        return

    current = love_percent.get(user_id, 0)
    love_percent[user_id] = min(current + 0.1, 100)
    save_love_data()

    if content.startswith("/nsfw"):
        nsfw_mode[user_id] = "on" in content
        await message.channel.send("🔞 NSFW mode is now **ON**." if nsfw_mode[user_id] else "🛡️ NSFW mode is now **OFF**.")
        return

    if content.startswith("/voice"):
        voice_mode[user_id] = "on" in content
        await message.channel.send("🔊 Voice mode is now **ON**." if voice_mode[user_id] else "🔇 Voice mode is now **OFF**.")
        return

    if content.startswith("/mode romantic"):
        romantic_mode[user_id] = "on" in content
        await message.channel.send("💖 Romantic mode is now **ON**." if romantic_mode[user_id] else "🚫 Romantic mode is now **OFF**.")
        return

    if content.startswith("/level") or content.startswith("/lovepercent"):
        percent = love_percent.get(user_id, 0.0)
        photo_dir = NSFW_PHOTO_DIR if (nsfw_mode.get(user_id, False) and percent >= 70) else DEFAULT_PHOTO_DIR
        photo_files = [f for f in os.listdir(photo_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if photo_files:
            await message.channel.send(file=discord.File(os.path.join(photo_dir, random.choice(photo_files))))
        await message.channel.send(f"💘 Your current love percent: {percent:.1f}%")
        return

    if bot.user in message.mentions:
        clean_content = content.replace(f"<@{bot.user.id}>", "").strip()
        memory = memory_data.get(user_id, "")
        reply = chat_with_groq(clean_content, memory, user_id)
        reply = re.sub(r"\b(bhai|bro)\b", "", reply, flags=re.IGNORECASE).strip().replace('\n', ' ')
        if len(reply) > 40:
            reply = reply[:40].rstrip() + "..."
        memory_data[user_id] = clean_content
        await message.channel.send(reply)

        if voice_mode.get(user_id, False):
            voice_path = text_to_voice(reply)
            if voice_path:
                await message.channel.send(file=discord.File(voice_path))
                os.remove(voice_path)

# Music Player
@bot.command()
async def play(ctx, url):
    if not ctx.author.voice:
        await ctx.send("⛔ Join a voice channel first!")
        return
    voice_channel = ctx.author.voice.channel
    vc = await voice_channel.connect()
    ydl_opts = {'format': 'bestaudio/best'}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        url2 = info['url']
        vc.play(discord.FFmpegPCMAudio(url2))
    await ctx.send(f"▶️ Playing: {info['title']}")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Music stopped.")

# Welcome Event
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="general")
    if channel:
        await channel.send(f"👋 Welcome {member.mention} to {member.guild.name}! 💖")

# Ready Event
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

bot.run(DISCORD_TOKEN)
