import discord
import logging
import logging.handlers
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord import FFmpegAudio
from pytube import Playlist, YouTube
import asyncio
import os
from VidDownloader import download, downloadHERALD
import queue
import Token
from discord.utils import get

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
token = Token.HiddenToken  # Pull the token from another file.
default_prefix = "!"  # Sets the default prefix for the bot.  This can be changed with a command.
prefix = default_prefix  # We will keep prefix/user data as instance data for now - this will be changed to be per server
bot = commands.Bot(command_prefix=prefix, intents=intents, case_insensitive=True)

intents = discord.Intents.default()  # Set bot permissions.
intents.message_content = True

client = discord.Client(intents=intents)

# Initialize global variables
MusicQueue = queue.Queue()
successful_join = False
vc = None
playingNOW = False
HeraldSongs = dict()  # Initialize a dictionary for Herald profiles
PlayingEvent = None

'''EVENTS'''
@bot.event
async def on_ready():
    """Debug Event: Triggers when bot is online."""
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_voice_state_update(user, before, after):
    if before.channel is None and after.channel:
       # User has connected to a VoiceChannel
        channel = after.channel

        if user.id in HeraldSongs.keys():
            channel = user.voice.channel  # Note the channel to play music in
            if playingNOW:
               vc.pause()  # Pauses music if any is playing currently.

            HeraldVC = await channel.connect()
            HeraldVC.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source=HeraldSongs[user.id][1]), after=lambda e: print("Done playing for user " + user.name + "."))

            while HeraldVC.is_playing():  # Sleep while the video finishes up playing.
                await asyncio.sleep(1)

            if playingNOW:
                vc.resume()  # resumes music if any was playing.
            else:
                await HeraldVC.disconnect()



'''
Example code for an event
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('&&&hello'):
        await message.channel.send('Hello!')
    await bot.process_commands(message)
'''

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

@bot.command(name="prefix_change")
async def pref_change(ctx, new_pref):
    """Changes the bot's command prefix to the given parameter"""
    global prefix
    prefix = new_pref  #TODO: The updated prefix is currently stored as instance data...I'd like to change that
    bot.command_prefix = prefix
    await ctx.send("Prefix has been set to: " + prefix)

@bot.command(name="Join")
async def join(ctx):
    """Bot joins the voice channel."""
    global successful_join
    global vc
    try:  #Checks if user is in a voice channel
        channel = ctx.author.voice.channel
        if not successful_join:
            vc = await channel.connect()
            successful_join = True
    except:
        await ctx.send("User must be in a voice channel")

    if vc is None or not vc.is_connected():
        await ctx.author.voice.channel.connect()
        vc = discord.utils.get(client.voice_clients, guild=ctx.guild)
    return vc

@bot.command(name="Leave")
async def leave(ctx):
    """Bot leaves the voice channel."""
    global successful_join
    global vc
    global MusicQueue

    if playingNOW:  # Clear the queue out and stop the player.
        MusicQueue = queue.Queue()
        vc.stop()
    # Then we will disconnect.
    await ctx.voice_client.disconnect()

    successful_join = False
    vc = None


@bot.command(name="Pause")
async def pause(ctx):
    global playingNOW
    global vc
    if playingNOW:
        # Pause audio
        vc.pause()
    else:
        # Don't try to pause if not playing now.  We'll have a null pointer exception.
        await ctx.send(ctx.author.mention + " No audio playing.  Play something with " + prefix + "Play")

@bot.command(name="Resume")
async def pause(ctx):
    global playingNOW
    global vc
    if playingNOW:
        vc.resume()  # resumes music if any was playing.
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  Maybe you meant to play something with " + prefix + "Play")

@bot.command(name="Skip")
async def skip_song(ctx):
    global playingNOW
    global vc
    global PlayingEvent
    print("Received Skip Command")
    if playingNOW:
        vc.stop()
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can skip it!")


@bot.command(name="Stop")
async def stop_playing(ctx):
    global playingNOW
    global vc
    global MusicQueue
    if playingNOW:
        MusicQueue = queue.Queue()
        vc.stop()
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can stop it!")


@bot.command(name="Play")
async def PlayEnqueue(ctx, url):
    """Command that user interacts with.  Adds urls to a music queue which are popped and played by PlayQ"""
    # Initialize global variables
    global playingNOW
    global MusicQueue
    global successful_join
    try:
        UserVoiceChannel = ctx.author.voice.channel  # Looks up the user channel.  If this fails (except), then we throw out the command since the user is not in voice.
        if successful_join:  # Execution will depend on whether the bot is already in the voice channel
            if "list" in str(url):
                p = Playlist(str(url))
                print("Queueing up a playlist..." + p.title)
                for vid in p.video_urls:
                    MusicQueue.put((ctx, vid))
                    #await ctx.send("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize()))
                    print("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize()))
                    #printf
            else:
                MusicQueue.put((ctx, url))  # Add song to queue
                vid = YouTube(str(url))
                await ctx.send(("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize())))
                print("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize()))
            VChan = ctx.voice_client.channel
        else:
            if "list" in str(url):
                p = Playlist(str(url))
                print("Queueing up a playlist..." + p.title)
                for vid in p.video_urls:
                    print("Attempting to enqueue")
                    MusicQueue.put((ctx, vid))
                    print("Enqueued: " + str(vid.title) + "at position " + str(MusicQueue.qsize()))
                    #await ctx.send("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize()))
            else:
                MusicQueue.put((ctx, url))
                vid = YouTube(str(url))
                await ctx.send("Enqueued: " + str(vid.title) + " at position " + str(MusicQueue.qsize()))
                print("Enqueued: " + str(vid.title) + "at position " + str(MusicQueue.qsize()))
                            # Video titles were not necessarily sanitized.  This may fix that issue.
            VChan = await join(ctx)

        if not playingNOW:
            await PlayQ(ctx, VChan)
    except Exception as e:
        print(e)
        await ctx.send("An exception occurred.  This may be because the user is not in the voice channel.")
        print("An exception occurred.  This may be because the user is not in the voice channel.")



#@bot.command(name="PlayQueue")  # Commenting this out in order to make it inaccessible to users.
async def PlayQ(ctx, voice):
    """Command used to play the queue of songs/videos enqueued with PlayEnqueue."""
    # Global variable declarations
    global playingNOW
    global vc
    global successful_join
    global PlayingEvent

    # Sets up an asynchronous event.
    PlayingEvent = asyncio.Event()
    PlayingEvent.set()

    playingNOW = True  # Initializes playing flag as true.
    print("entering PlayQ")
    previousFilePath = ""
    while True:  # Loops forever until we break (when queue is empty)
        print(MusicQueue.qsize())
        await PlayingEvent.wait()  # Wait until the previous song is done playing.

        if len(previousFilePath) > 0: # If we have a previous file path (a song was played before this) delete the file.
            #os.remove(previousFilePath)
            print("Removed File.")

        PlayingEvent.clear()  # Reset the event

        if MusicQueue.qsize() == 0:  # Check if the queue is empty
            playingNOW = False
            await ctx.voice_client.disconnect()  # If queue is empty, we disconnect from voice.
            successful_join = False
            break

        print("PLAY SONG NOW")
        Current = MusicQueue.get()  # Pop a song from the queue
        file = download(Current[1])  # Download the song that was linked.
        CurrentSongFilePath = file[0]  # Take the file path for the downloaded song.
        print(CurrentSongFilePath)

        # Begin playing the audio file.  Executable will need to be changed when running on server.
        voice.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source=CurrentSongFilePath), after=lambda e: PlayingEvent.set())

        # Send out status messages.
        await ctx.send("NOW PLAYING: " + file[1])  # file
        print("NOW PLAYING: " + file[1])
        print("Finished Playing " + file[1] + " Deleting file and moving to next song:")
        previousFilePath = CurrentSongFilePath


@bot.command(name = "HeraldSet", description = "Sets up a herald bot profile.  Provide a short YouTube URL to play every time you join voice.")
async def HeraldSet(ctx, url):
    """Sets the Herald Theme for the user."""
    # Initialize global variables
    global HeraldSongs

    HeraldUser = ctx.author
    HeraldKey = HeraldUser.id  # Takes the user's id.  This will be used as the key for the dictionary.

    try:
        file = downloadHERALD(url)  # Returns tuple containing the filepath and file name
    except:
        await ctx.send("ERROR: Herald Theme download failed.")
        print("ERROR: Herald Theme download failed.")

    HeraldSongs[HeraldKey] = (url, file[0], file[1])  # Stores the file as a tuple: URL (backup), filepath, file name.

    userMentionTag = HeraldUser.mention
    await ctx.send(userMentionTag + "Success!  Your Herald theme has been changed to: " + HeraldSongs[HeraldKey][2])

@bot.command(name = "HeraldTheme", description = "Returns the user's herald theme.")
async def HeraldTheme(ctx):
    """Returns the user's Herald Theme if one is set."""
    global HeraldSongs
    try:
        HeraldID = ctx.author.id
        userMentionTag = ctx.author.mention
        if HeraldID in HeraldSongs.keys():
            await ctx.send(userMentionTag + "Your Herald theme is: " + HeraldSongs[HeraldID][2] + ", LINK: " + HeraldSongs[HeraldID][0])

        else:
            await ctx.send(userMentionTag + "You do not have a Herald theme set.  To set one use the HeraldSet command, along with a link to a short youtube video.")

    except:
        await ctx.send("ERROR: HERALD THEME CHECK FAILED.")
        print("ERROR: HERALD THEME CHECK FAILED.")


"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
bot.run(token)