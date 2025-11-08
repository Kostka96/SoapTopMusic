import os

import discord
from discord.ext import commands
import asyncio
import yt_dlp as youtube_dl
import functools
from dotenv import load_dotenv
print("SoapTopMusic v1.0")
load_dotenv()
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# Настройки для youtube_dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # IPv4
}

ffmpeg_options = {
    'executable': r'E:\PyCharmProject\SoapTopMusic\FFmpeg\bin\ffmpeg.exe',  # Указываем путь к ffmpeg
    'options': '-vn'
}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        return cls(discord.FFmpegPCMAudio(data['url'], executable=ffmpeg_options['executable'], options=ffmpeg_options['options']), data=data)



intents = discord.Intents.default()
#intents.members = True   # Отключаем интент для работы с участниками сервера
#intents.presences = True  # Включаем интент для работы с присутствиями
intents.message_content = True  # Для чтения сообщений
intents.voice_states = True  # Для работы с голосовыми каналами

# Инициализация Discord-бота
discord_bot = commands.Bot(command_prefix='$$', intents=intents)

# Очередь треков для каждого сервера
queues = {}

# Событие, которое срабатывает при успешном запуске бота
@discord_bot.event
async def on_ready():
    print(f'Бот {discord_bot.user.name} успешно запущен!')

    activity = discord.CustomActivity(name="Жирный гей")  # Здесь можно поменять текст
    await discord_bot.change_presence(status=discord.Status.online, activity=activity)
async def play_next(ctx):
    """Функция вызывается автоматически после завершения текущего трека."""
    if ctx.guild.id in queues and not queues[ctx.guild.id].empty():
        next_song = await queues[ctx.guild.id].get()
        ctx.voice_client.play(next_song, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), discord_bot.loop))
        await ctx.send(f'Сейчас играет: {next_song.title}')
    else:
        await ctx.send("Очередь пуста.")
# Команда для подключения к голосовому каналу
@discord_bot.command()
async def join(ctx):
    """Подключение к голосовому каналу."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Бот подключился к каналу {channel.name}!")
    else:
        await ctx.send("Ты не находишься в голосовом канале!")

# Команда для отключения от голосового канала
@discord_bot.command()
async def leave(ctx):
    """Отключение от голосового канала и очистка очереди."""
    if ctx.voice_client:
        if ctx.guild.id in queues:
            queues[ctx.guild.id] = asyncio.Queue()  # Очистка очереди
        await ctx.voice_client.disconnect()
        await ctx.send("Бот отключился от голосового канала и очистил очередь.")
    else:
        await ctx.send("Бот не подключен к голосовому каналу.")

@discord_bot.command()
async def play(ctx, url):
    """Добавление трека в очередь и воспроизведение."""
    if not ctx.voice_client:
        await ctx.invoke(join)

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=discord_bot.loop, stream=True)

            # Если очередь для сервера не существует, создаём
            if ctx.guild.id not in queues:
                queues[ctx.guild.id] = asyncio.Queue()

            await queues[ctx.guild.id].put(player)

            if not ctx.voice_client.is_playing():  # Если сейчас ничего не играет, запускаем трек
                await play_next(ctx)
            else:
                await ctx.send(f'Добавлено в очередь: {player.title}')
        except Exception as e:
            await ctx.send(f'Ошибка воспроизведения: {str(e)}')

@discord_bot.command()
async def skip(ctx):
    """Пропуск текущего трека и запуск следующего из очереди."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Пропускаем трек...")
        await play_next(ctx)
    else:
        await ctx.send("Сейчас ничего не играет.")

# Команда для остановки воспроизведения
@discord_bot.command()
async def stop(ctx):
    """Полностью останавливает воспроизведение и очищает очередь."""
    if ctx.voice_client:
        ctx.voice_client.stop()
        if ctx.guild.id in queues:
            queues[ctx.guild.id] = asyncio.Queue()  # Очистка очереди
        await ctx.send("Воспроизведение остановлено, очередь очищена.")
    else:
        await ctx.send("Бот не подключен к голосовому каналу.")

# Проверка, что бот подключен к голосовому каналу перед воспроизведением
@play.before_invoke
@stop.before_invoke
@skip.before_invoke
async def ensure_voice(ctx):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Ты не находишься в голосовом канале!")
            raise commands.CommandError("Автор команды не подключен к голосовому каналу.")

### --- Запуск --- ###
if __name__ == "__main__":
    # Запускаем Discord-бота
    discord_bot.run(DISCORD_TOKEN)
