import asyncio

import discord
import yt_dlp as youtube_dl

from discord.ext import commands
from qwer import Token

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

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
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
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
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_channel_id = None  # 음악 전용 채널 ID를 저장

    @commands.command()
    async def join(self, ctx):
        """Joins a voice channel"""

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @commands.command()
    async def pause(self, ctx):
        ''' 음악을 일시정지 할 수 있습니다. '''

        if ctx.voice_client.is_paused() or not ctx.voice_client.is_playing():
            return await ctx.send("음악이 이미 일시 정지 중이거나 재생 중이지 않습니다.")

        ctx.voice_client.pause()

    @commands.command()
    async def resume(self, ctx):
        ''' 일시정지된 음악을 다시 재생할 수 있습니다. '''

        if ctx.voice_client.is_playing() or not ctx.voice_client.is_paused():
            return await ctx.send("음악이 이미 재생 중이거나 재생할 음악이 존재하지 않습니다.")

        ctx.voice_client.resume()

    @commands.command()
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Sets the music-only text channel."""
        self.music_channel_id = channel.id
        await ctx.send(f"Music channel set to {channel.mention}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if the message is in the music channel
        if self.music_channel_id and message.channel.id == self.music_channel_id:
            if not message.author.voice:
                await message.channel.send("You need to be in a voice channel to play music.")
                return

            voice_client = message.guild.voice_client

            # Join the author's voice channel if not already connected
            if not voice_client:
                await message.author.voice.channel.connect()
            elif voice_client.channel != message.author.voice.channel:
                await message.channel.send("I'm already connected to another voice channel.")
                return

            # Attempt to play the requested song
            try:
                async with message.channel.typing():
                    player = await YTDLSource.from_url(message.content, loop=self.bot.loop, stream=True)
                    voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

                await message.channel.send(f'Now playing: {player.title}')
            except Exception as e:
                await message.channel.send(f"An error occurred: {str(e)}")

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='Relatively simple music bot example',
    intents=intents,
)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(Token)


asyncio.run(main())
