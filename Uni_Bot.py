import discord
import logging
import logging.handlers
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord import FFmpegAudio
import asyncio
import os
from VidDownloader import download
import queue
import Token

"""ERROR LOGGING"""
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    maxBytes=32 * 1024 * 1024,  # 32 MiB
    backupCount=5,  # Rotate through 5 files
)
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)

"""SETUP"""

###VARIABLE INITIALIZATION###
intents = discord.Intents.all()
# intents.message_content = True
token = Token.HiddenToken
default_prefix = "!"
prefix = default_prefix  # We will keep prefix/user data as instance data for now - this will be changed to be per server
bot = commands.Bot(command_prefix='$', intents=intents)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MusicQueue = queue.Queue()
successful_join = False
vc = None
playingNOW = False

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


# - May not need this
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('&&&hello'):
        await message.channel.send('Hello!')
    await bot.process_commands(message)


"""FUNCTIONS"""


class MyHelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        e = discord.Embed(color=discord.Color.blurple(), description='')
        for page in self.paginator.pages:
            e.description += page
        await destination.send(embed=e)


bot.help_command = MyHelpCommand()


@bot.command()
async def hello(ctx):
    await ctx.send(ctx.author.mention + " hello!")


@bot.command(name="test")
async def test(ctx):
    await ctx.send("Test")


@bot.command()
async def test2(ctx, arg):
    await ctx.send(arg)


@bot.command(name="prefix_change")
async def pref_change(ctx, new_pref):
    """Changes the bot's command prefix to the given parameter"""
    global prefix
    prefix = new_pref  #TODO: The updated prefix is currently stored as instance data...I'd like to change that
    bot.command_prefix = prefix
    await ctx.send("Prefix has been set to: " + prefix)

@bot.command(name="PlayTune1")
async def play_tune1(ctx):
    """Plays a preset tune.  TESTING FUNCTION."""
    successful_join = join(ctx)
    if successful_join:  # Only proceed with music if user is actually in vc
        channel = ctx.author.voice.channel  # Note the channel to play music in
        vc = await channel.connect()
        player = vc.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source="D:/kevin/Git Repos/Unicron_Bot/TestTune.mp3"), after=lambda: print('done'))
        player.start()
        while not player.is_done():
            await asyncio.sleep(1)
        player.stop()
    else:
        await ctx.send("User is not in a voice channel.")

@bot.command(name="Join")
async def join(ctx):
    global successful_join
    global vc
    try:  #Checks if user is in a voice channel
        channel = ctx.author.voice.channel
        if not successful_join:
            vc = await channel.connect()
            successful_join = True
        return True
    except:
        await ctx.send("User must be in a voice channel")
        return True

@bot.command(name="Leave")
async def leave(ctx):
    global successful_join
    global vc
    await ctx.voice_client.disconnect()
    successful_join = False
    vc = None
    #TODO: Add case for deleting music file after leave
file_path = os.path.realpath(__file__)

@bot.command(name="DownloadAudio")
async def dl(ctx, url):
    download(url)


@bot.command(name="PlayNOW")
async def PlayYT(ctx, url):
    file = download(url)
    successful_join = join(ctx)
    if successful_join:  # Only proceed with music if user is actually in vc
        channel = ctx.author.voice.channel  # Note the channel to play music in
        vc = await channel.connect()
        player = vc.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source="D:/kevin/Git Repos/Unicron_Bot/"+ file), after=lambda: print('done'))
        player.start()
        while not player.is_done():
            await asyncio.sleep(1)
        player.stop()
        os.remove(file)  #TODO: File isn't actually getting deleted
    else:
        await ctx.send("User is not in a voice channel.")

    #TODO: Implement herald bot functionality

@bot.command(name="Play")
async def PlayEnqueue(ctx, url):
    file = download(url)
    global successful_join
    global vc
    await join(ctx)
    if successful_join:  # Only proceed with music if user is actually in vc
        global MusicQueue
        MusicQueue.put((ctx, file))
    else:
        await ctx.send("User is not in a voice channel.")
    if not playingNOW:
        await PlayQ(ctx)


@bot.command(name="PlayQueue")
async def PlayQ(ctx):
    global playingNOW
    global vc
    playingNOW = True
    while not MusicQueue.empty():
        print("PLAY SONG NOW")
        Current = MusicQueue.get()
        vc = Current[0].author.voice.channel
        CurrentSongFilePath = Current[1]
        player = vc.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe",source=CurrentSongFilePath))
        player.start()
        while not player.is_done():
            await asyncio.sleep(1)
        player.stop()
        print(Current[1])
        os.remove(CurrentSongFilePath)

"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
bot.run(token)