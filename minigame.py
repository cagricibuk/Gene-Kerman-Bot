import discord
from discord.ext import commands
import random
import asyncio
import json
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Intents ayarları
intents = discord.Intents.default()
intents.message_content = True

# Bot komutları için bir prefix belirleyin
bot = commands.Bot(command_prefix='!', intents=intents)

# Senaryoları yükle
def load_scenarios():
    with open('scenarios.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

scenarios = load_scenarios()

# Botun hazır olduğunu bildiren bir olay
@bot.event
async def on_ready():
    print(f'Bot {bot.user} olarak giriş yaptı.')

#minigame command
@bot.command(name='minigame')
async def mini_game(ctx):
    # Kategorileri seçmek için
    category = random.choice(list(scenarios.keys()))
    scenario_list = scenarios[category]
    scenario = random.choice(scenario_list)
    
    question = scenario['question']
    options = scenario['options']
    results = scenario['results']

    # Soruyu ve seçenekleri gönder
    await ctx.send(f"{question}\nSeçenekler:\n" + "\n".join([f"{key}: {value}" for key, value in options.items()]))

    def check(m):
        return m.author == ctx.author and m.content.upper() in options.keys()

    # Kullanıcının cevabını bekle
    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send('Zaman aşımına uğradı! Cevap vermen çok uzun sürdü.')
    else:
        user_choice = msg.content.upper()
        if user_choice in results:
            outcome = random.choice(results[user_choice])
            await ctx.send(outcome)
        else:
            await ctx.send('Geçersiz seçenek! Lütfen geçerli bir seçenek girin.')

# Botu çalıştır
bot.run(TOKEN)
