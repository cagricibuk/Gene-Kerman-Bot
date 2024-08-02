import discord
from discord.ext import commands, tasks
import random
import asyncio
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Intents ayarları
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.typing = True
intents.messages = True
intents.message_content = True

# Bot komutları için bir prefix belirleyin
bot = commands.Bot(command_prefix='!', intents=intents)

# Senaryoları yükle
def load_scenarios():
    with open('scenarios.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

scenarios = load_scenarios()

# JSON dosyasını yükle veya boş dictionary döndür
def load_play_times():
    try:
        with open('play_times.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        # Dosya yoksa veya JSONDecodeError hatası alınırsa boş bir dictionary döndür
        return {}

def save_play_times(play_times):
    with open('play_times.json', 'w') as f:
        json.dump(play_times, f, indent=4)

def calculate_total_play_time(data):
    total_duration = 0
    for session in data['sessions']:
        start_time = datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
        if 'end_time' in session:
            end_time = datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
            play_duration = end_time - start_time
            total_duration += play_duration.total_seconds()
        else:
            play_duration = datetime.now() - start_time
            total_duration += play_duration.total_seconds()
    return total_duration

async def announce_top_players():
    play_times = load_play_times()
    total_play_times = {}

    for user_id, data in play_times.items():
        if user_id == 'start_date':
            continue
        total_duration = calculate_total_play_time(data)
        total_play_times[user_id] = {'name': data['name'], 'total_duration': total_duration}

    top_players = sorted(total_play_times.items(), key=lambda x: x[1]['total_duration'], reverse=True)[:5]
    
    message = "Etkinlikte en çok oynayanlar:\n"
    for i, (user_id, player) in enumerate(top_players, 1):
        hours, minutes = divmod(player['total_duration'] / 60, 60)
        message += f"{i}. {player['name']} - {int(hours)} saat {int(minutes)} dakika\n"

    # Kanala mesaj gönder
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == 'ksp-log':  # 'ksp-log' isimli kanala mesaj gönderme
                await channel.send(message)
                break

@tasks.loop(hours=24)
async def daily_update():
    await announce_top_players()

@daily_update.before_loop
async def before_daily_update():
    await bot.wait_until_ready()
    print("Bot aktif, günlük güncelleme döngüsü başlıyor.")

@tasks.loop(hours=3)
async def hourly_update():
    play_times = load_play_times()
    start_date = datetime.strptime(play_times['start_date'], '%Y-%m-%d %H:%M:%S')
    time_remaining = datetime.now() - start_date
    hours_remaining = 168 - time_remaining.total_seconds() // 3600  # 168 saat = 7 gün

    if hours_remaining <= 0:
        await announce_top_players()
        hourly_update.stop()  # Duyuru yapıldıktan sonra 3 saatlik döngüyü durdur
        daily_update.stop()   # Duyuru yapıldıktan sonra günlük döngüyü durdur
    else:
        message = f"Etkinliğin bitmesine {int(hours_remaining)} saat kaldı."
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.name == 'ksp-log':  # 'ksp-log' isimli kanala mesaj gönderme
                    await channel.send(message)
                    break

@hourly_update.before_loop
async def before_hourly_update():
    await bot.wait_until_ready()
    print("Bot aktif, 3 saatlik güncelleme döngüsü başlıyor.")

@bot.event
async def on_ready():
    print(f'Bot {bot.user} olarak giriş yaptı')
    play_times = load_play_times()
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Başlangıç tarihini 15 Temmuz 2024 23:17:43 olarak ayarlama
    if 'start_date' not in play_times:
        play_times['start_date'] = '2024-07-15 23:17:43'
        save_play_times(play_times)
    else:
        # Botun son çalıştırılmasından sonra geçen günlerin hesaplanması
        start_date = datetime.strptime(play_times['start_date'], '%Y-%m-%d %H:%M:%S')
        days_passed = (datetime.now() - start_date).days + 1

        # Eğer geçen günler 1'den fazlaysa, günlük güncellemeyi bir kez çalıştır
        if days_passed > 1:
            await daily_update()

    # KSP oynayan üyeleri kaydet
    for guild in bot.guilds:
        for member in guild.members:
            playing_ksp = lambda presence: presence.activity and presence.activity.name == "Kerbal Space Program"
            if playing_ksp(member):
                member_id_str = str(member.id)
                if member_id_str not in play_times:
                    play_times[member_id_str] = {'name': member.name, 'sessions': []}
                play_times[member_id_str]['sessions'].append({'start_time': start_time})
                await send_log(member.guild, f"{member.name} oynamaya başladı (bot başlangıcı): Kerbal Space Program")
                print(f"{member.name} (ID: {member.id}) bot başlangıcında KSP oynuyor ve kayıt edildi.")
    
    save_play_times(play_times)

    # Günlük güncellemeyi başlat
    daily_update.start()
    # 3 saatlik güncellemeyi başlat
    hourly_update.start()

@bot.event
async def on_presence_update(before, after):
    play_times = load_play_times()

    # Kullanıcı KSP oynuyor mu diye kontrol et
    playing_ksp = lambda activities: any(activity.name == "Kerbal Space Program" for activity in activities)

    # Kullanıcı KSP oynamaya başladı
    if not playing_ksp(before.activities) and playing_ksp(after.activities):
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        member_id_str = str(after.id)
        if member_id_str not in play_times:
            play_times[member_id_str] = {'name': after.name, 'sessions': []}
        play_times[member_id_str]['sessions'].append({'start_time': start_time})
        save_play_times(play_times)
        await send_log(after.guild, f"{after.name} oynamaya başladı: Kerbal Space Program")
        print(f"{after.name} (ID: {after.id}) oynamaya başladı ve kayıt edildi.")

    # Kullanıcı KSP oynamayı bıraktı
    elif playing_ksp(before.activities) and not playing_ksp(after.activities):
        print(f"{before.id} Oynamayı bıraktı")
        member_id_str = str(before.id)
        if member_id_str in play_times:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            last_session = play_times[member_id_str]['sessions'][-1]
            start_time = datetime.strptime(last_session['start_time'], '%Y-%m-%d %H:%M:%S')
            play_duration = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S') - start_time

            hours, remainder = divmod(play_duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)

            last_session['end_time'] = end_time
            last_session['duration_hours'] = int(hours)
            last_session['duration_minutes'] = int(minutes)
            save_play_times(play_times)

            duration_str = f"{int(hours)} saat {int(minutes)} dakika"
            await send_log(before.guild, f"{before.name} oynamayı bıraktı: Kerbal Space Program. Oturum süresi: {duration_str}")
            print(f"{before.name} (ID: {before.id}) oynamayı bıraktı ve oturum süresi kaydedildi: {duration_str}")
        else:
            print("Kayıtlarda yok")

async def send_log(guild, message):
    for channel in guild.text_channels:
        if channel.name == 'ksp-log':  # 'ksp-log' isimli kanala mesaj gönderme
            await channel.send(message)
            break    

#minigame command
@bot.command(name='minigame')
async def mini_game(ctx):
    # Kategorileri seçmek için
    category = random.choice(list(scenarios.keys()))
    scenario = random.choice(scenarios[category])

    question = scenario["question"]
    options = scenario["options"]

    options_text = "\n".join([f"{i+1}. {option}" for i, option in enumerate(options)])

    await ctx.send(f"Soru: {question}\nSeçenekler:\n{options_text}\nLütfen cevabınızı numara ile belirtin (örneğin: 1, 2, 3, 4)")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit() and 1 <= int(m.content) <= len(options)

    try:
        answer = await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("Cevap vermek için çok geç kaldınız.")
        return

    chosen_option = options[int(answer.content) - 1]
    outcome = scenario["outcomes"][chosen_option]

    await ctx.send(f"{ctx.author.mention}, {chosen_option} seçeneğini seçtiniz. Sonuç: {outcome}")

# Botu çalıştır
bot.run(TOKEN)
