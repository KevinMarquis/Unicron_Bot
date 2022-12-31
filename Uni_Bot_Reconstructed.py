import discord
import logging.handlers
from discord.ext import commands
from discord import FFmpegPCMAudio
from pytube import Playlist, YouTube
import asyncio
from VidDownloader import download, downloadHERALD
import queue
import Token
import os
import json

#region ERROR LOGGING
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
#endregion

#region Setup
intents = discord.Intents.default()  # Set bot permissions.
intents.message_content = True

token = Token.HiddenToken  # Pull the token from another file.
default_prefix = "!"  # Sets the default prefix for the bot.  This can be changed with a command.
prefix = default_prefix  # We will keep prefix/user data as instance data for now - this will be changed to be per server
bot = commands.Bot(command_prefix=prefix, intents=intents, case_insensitive=True)
client = discord.Client(intents=intents)

ServerProfiles = dict()  # Initializes a dictionary with server ids as keys to another dictionary, with particular data.

@bot.event
async def on_ready():
    """Debug Event: Triggers when bot is online."""
    print(f'We have logged in as {bot.user}')

    print("Setting up Guild Profiles")
    for guild in bot.guilds:
        ServerProfiles[guild.id] = Guild_Profile(guild)
        print("This server has ID and Name: ")
        print(guild.id)
        print(guild.name + "\n")
        BackupFileName = str(guild.id) + ".json"
        if os.path.exists("HeraldBackups/" + BackupFileName):
            with open("HeraldBackups/" + BackupFileName, 'r') as backup:
                ServerProfiles[guild.id].HeraldSongs = json.load(backup)
                print("Retreived Herald Profiles!")

            print("Restoring Herald Videos!")
            for userID in ServerProfiles[guild.id].HeraldSongs.keys():
                HeraldProfile = ServerProfiles[guild.id].HeraldSongs[userID]
                try:
                    File = downloadHERALD(HeraldProfile[0])
                    HeraldProfile[1] = File[0]
                    HeraldProfile[2] = File[1]
                except Exception as e:
                    print("ERROR in Restoring Herald Profile for USER ID: " + userID)
                    print(e)

            newHeraldProfileDict = {}
            for OldKey in ServerProfiles[guild.id].HeraldSongs.keys():
                try:
                    NewKey = int(OldKey)
                    newHeraldProfileDict[NewKey] = ServerProfiles[guild.id].HeraldSongs[OldKey]
                except ValueError:
                    print("Error in adapting HeraldSongs from JSON.")
            ServerProfiles[guild.id].HeraldSongs = newHeraldProfileDict

    # Add a case for pulling from saved data (i.e. restoring Herald Profiles).  We'll get to that later though.



#endregion

class Guild_Profile():
    def __init__(self, Guild):
        self.Guild = Guild
        self.HeraldSongs = dict() # Initialize a dictionary for Herald profiles
        self.MusicQueue = queue.Queue()
        self.successful_join = False
        self.vc = None
        self.playingNOW = False
        self.PlayingEvent = asyncio.Event()

    def __str__(self):
        """Creates a readble format to see the Guild Profile Data"""
        StringtoReturn = ""
        StringtoReturn += "\n\n--------------------------"
        StringtoReturn += "\nSERVER PROFILE FOR: " + self.Guild.name
        StringtoReturn += "\nSUCCESSFUL JOIN: " + str(self.successful_join)
        StringtoReturn += "\nPLAYING NOW: " + str(self.playingNOW)

        StringtoReturn += "\nMUSIC QUEUE:"
        StringtoReturn += "\n     CURRENT QUEUE SIZE: " + str(self.MusicQueue.qsize())

        StringtoReturn += "\nHERALD USERS: "
        StringtoReturn += "\n     CURRENT NUMBER OF PROFILES: " + str(len(self.HeraldSongs))
        for userID in self.HeraldSongs.keys():
            StringtoReturn += "\n" + str(userID)

        StringtoReturn += "\n\nEND SERVER PROFILE\n--------------------------\n"
        return StringtoReturn


#region Help Setup
class MyHelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        e = discord.Embed(color=discord.Color.blurple(), description='')
        for page in self.paginator.pages:
            e.description += page
        await destination.send(embed=e)


bot.help_command = MyHelpCommand()
#endregion

#region Herald Functionality
@bot.event
async def on_voice_state_update(user, before, after):
    global ServerProfiles
    if before.channel is None and after.channel is not None:
       # User has connected to a VoiceChannel
        channel = after.channel
        ThisServerProfile = ServerProfiles[after.channel.guild.id]

        if user.id in ThisServerProfile.HeraldSongs.keys():
            channel = user.voice.channel  # Note the channel to play music in
            if ThisServerProfile.playingNOW:
                ThisServerProfile.vc.pause()  # Pauses music if any is playing currently.

            HeraldVC = await channel.connect()
            HeraldVC.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source= ThisServerProfile.HeraldSongs[user.id][1]), after=lambda e: print("Done playing for user " + user.name + "."))

            while HeraldVC.is_playing():  # Sleep while the video finishes up playing.
                await asyncio.sleep(1)

            if ThisServerProfile.playingNOW:
                ThisServerProfile.vc.resume()  # resumes music if any was playing.
            else:
                await HeraldVC.disconnect()


@bot.command(name = "HeraldSet", description = "Sets up a herald bot profile.  Provide a short YouTube URL to play every time you join voice.")
async def HeraldSet(ctx, url):
    """Sets the Herald Theme for the user."""
    # Initialize global variables
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    HeraldUser = ctx.author
    HeraldKey = HeraldUser.id  # Takes the user's id.  This will be used as the key for the dictionary.

    try:
        file = downloadHERALD(url)  # Returns tuple containing the filepath and file name
    except:
        await ctx.send("ERROR: Herald Theme download failed.")
        print("ERROR: Herald Theme download failed.")

    ThisServerProfile.HeraldSongs[HeraldKey] = (url, file[0], file[1])  # Stores the file as a tuple: URL (backup), filepath, file name.

    userMentionTag = HeraldUser.mention
    await ctx.send(userMentionTag + "Success!  Your Herald theme has been changed to: " + ThisServerProfile.HeraldSongs[HeraldKey][2])

    if not os.path.exists("HeraldBackups"):
        os.makedirs("HeraldBackups")
    BackupFile = "HeraldBackups/" + str(ThisServerProfile.Guild.id) + ".json"
    with open(BackupFile, "w") as outfile:
        json.dump(ThisServerProfile.HeraldSongs, outfile)

@bot.command(name = "HeraldTheme", description = "Returns the user's herald theme.")
async def HeraldTheme(ctx):
    """Returns the user's Herald Theme if one is set."""
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    try:
        print(str(ctx.author.id))
        print(ThisServerProfile.HeraldSongs)
        HeraldID = ctx.author.id
        userMentionTag = ctx.author.mention
        if HeraldID in ThisServerProfile.HeraldSongs.keys():
            await ctx.send(userMentionTag + "Your Herald theme is: " + ThisServerProfile.HeraldSongs[HeraldID][2] + ", LINK: " + ThisServerProfile.HeraldSongs[HeraldID][0])

        else:
            await ctx.send(userMentionTag + "You do not have a Herald theme set.  To set one use the HeraldSet command, along with a link to a short youtube video.")

    except:
        await ctx.send("ERROR: HERALD THEME CHECK FAILED.")
        print("ERROR: HERALD THEME CHECK FAILED.")
#endregion

#region Generic Commands
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

#endregion

#region Voice_Channel_Commands
@bot.command(name="Join")
async def join(ctx):
    """Bot joins the voice channel."""
    global ServerProfiles

    print("\n\nTest values: \n")
    print(ctx.message.guild)
    print(ctx.message.guild.name + "\n\n")


    ThisServerProfile = ServerProfiles[ctx.message.guild.id]

    try:  #Checks if user is in a voice channel
        channel = ctx.author.voice.channel
        if not ThisServerProfile.successful_join:
            ThisServerProfile.vc = await channel.connect()
            ThisServerProfile.successful_join = True
    except:
        await ctx.send("User must be in a voice channel")

    if ThisServerProfile.vc is None or not ThisServerProfile.vc.is_connected():
        await ctx.author.voice.channel.connect()
        ThisServerProfile.vc = discord.utils.get(client.voice_clients, guild=ctx.guild)
    return ThisServerProfile.vc

@bot.command(name="Leave")
async def leave(ctx):
    """Bot leaves the voice channel."""
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    print(str(ThisServerProfile))

    if ThisServerProfile.playingNOW:  # Clear the queue out and stop the player.
        ThisServerProfile.MusicQueue = queue.Queue()
        if ThisServerProfile.vc:
            ThisServerProfile.vc.stop()
    # Then we will disconnect.
    #await ctx.voice_client.disconnect()
    await ThisServerProfile.vc.disconnect()

    ThisServerProfile.successful_join = False
    ThisServerProfile.vc = None
    ThisServerProfile.PlayingNOW = False
    ThisServerProfile.PlayingEvent.clear()


@bot.command(name="Pause")
async def pause(ctx):
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        # Pause audio
        ThisServerProfile.vc.pause()
    else:
        # Don't try to pause if not playing now.  We'll have a null pointer exception.
        await ctx.send(ctx.author.mention + " No audio playing.  Play something with " + prefix + "Play")

@bot.command(name="Resume")
async def resume(ctx):
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        ThisServerProfile.vc.resume()  # resumes music if any was playing.
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  Maybe you meant to play something with " + prefix + "Play")

@bot.command(name="Skip")
async def skip_song(ctx):
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    print("Received Skip Command")
    if ThisServerProfile.playingNOW:
        ThisServerProfile.vc.stop()
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can skip it!")


@bot.command(name="Stop")
async def stop_playing(ctx):
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        ThisServerProfile.MusicQueue = queue.Queue()
        ThisServerProfile.vc.stop()
        ThisServerProfile.playingNOW = False
    else:
        print("Music not playing.  Current queue size: " + str(ThisServerProfile.MusicQueue.qsize()))
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can stop it!")


@bot.command(name="Play")
async def PlayEnqueue(ctx, url):
    """Command that user interacts with.  Adds urls to a music queue which are popped and played by PlayQ"""
    # Initialize global variables
    global ServerProfiles
    print("A")
    try:  # Check that the command sender is in a voice channel.  If not, ignore the command.
        UserVoiceChannel = ctx.author.voice.channel  # Looks up the user channel.  If this fails (except), then we throw out the command since the user is not in voice.
    except Exception as e:
        await ctx.send("An exception occurred.  This may be because the user is not in the voice channel.")
        print("An exception occurred.  This may be because the user is not in the voice channel.")
        print(e)
        return  # Throw out this command

    try:
        ThisServerProfile = ServerProfiles[ctx.message.guild.id]
        print("B")

        if "list" in str(url):
            p = Playlist(str(url))
            await  ctx.send("Queueing up a playlist..." + p.title)
            print("Queueing up a playlist..." + p.title)
            for vid in p.video_urls:
                ThisServerProfile.MusicQueue.put((ctx, vid))
                print("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize()))
        else:
            ThisServerProfile.MusicQueue.put((ctx, url))  # Add song to queue
            vid = YouTube(str(url))
            await ctx.send(("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize())))
            print("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize()))

        if not ThisServerProfile.successful_join:
            await join(ctx)
        print("C")
        print(ThisServerProfile.playingNOW)

        if not ThisServerProfile.playingNOW:
            await PlayQ(ctx, ThisServerProfile.vc)
    except Exception as e:
        await ctx.send("An exception occurred.  Plese check the log for more details.")
        print("An exception occurred.... See Below: ")
        print(e)


async def PlayQ(ctx, voice):
    """Command used to play the queue of songs/videos enqueued with PlayEnqueue."""
    # Global variable declarations
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    ThisServerProfile.PlayingEvent.set()
    ThisServerProfile.playingNOW = True
    print("entering PlayQ")

    async def WaitAndDelete(event, FilePath):
        print("1")
        await event.wait()
        print("2")

        print("Finished Playing. Deleting file and moving to next song:")
        os.remove(FilePath)

    while True:
        print("3")

        ThisServerProfile.PlayingEvent.clear()
        Current = ThisServerProfile.MusicQueue.get()  # Pop a song from the queue
        file = download(Current[1])  # Download the song that was linked.
        CurrentSongFilePath = file[0]  # Take the file path for the downloaded song.
        print("4")
        waiter_task = asyncio.create_task(WaitAndDelete(ThisServerProfile.PlayingEvent, CurrentSongFilePath))
        print("5")

        ThisServerProfile.vc.play(FFmpegPCMAudio(executable="D:/kevin/Git Repos/Unicron_Bot/ffmpeg-2022-10-27-git-00b03331a0-full_build/bin/ffmpeg.exe", source=CurrentSongFilePath), after=lambda e: ThisServerProfile.PlayingEvent.set())
        await ctx.send("NOW PLAYING: " + file[1])
        print("NOW PLAYING: " + file[1])
        print("6")


        await waiter_task  # Wait until the waiter task is finished - which is when the music stops playing
        print("7")

        if ThisServerProfile.MusicQueue.qsize() == 0:
            print("8")
            ThisServerProfile.playingNOW = False
            await leave(ctx)  # This should be fine.  Just wanna leave it comented until I work out the other issue.
            break

#endregion

"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
bot.run(token)