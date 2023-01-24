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
import time

# region ERROR LOGGING
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
# endregion

# region Setup
intents = discord.Intents.default()  # Set bot permissions.
intents.message_content = True
#This may need to be commented out for linux ^

token = Token.HiddenToken  # Pull the token from another file.
ServerProfiles = dict()  # Initializes a dictionary with server ids as keys to another dictionary, with particular data.
ServerPrefixes = dict()  # Initializes a dictionary with server ids as keys to the command prefix for that server.
CWD = os.getcwd()
FFmpegPCMAudio_FilePath = os.path.join(CWD, "ffmpeg-2022-10-27-git-00b03331a0-full_build", "bin", "ffmpeg.exe")  #WINDOWS
#FFmpegPCMAudio_FilePath = os.path.join("/usr", "bin", "ffmpeg")  # RASBIAN/LINUX

def get_prefix(client, message):
    global ServerPrefixes
    if message.guild.id in ServerPrefixes:  # Checks for a custom prefix
        return ServerPrefixes[message.guild.id]
    else:
        return "!"  # Default Prefix


bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True)
client = discord.Client(intents=intents)


@bot.event
async def on_ready():
    """Debug Event: Triggers when bot is online."""

    print(f'We have logged in as {bot.user}')

    global ServerProfiles
    global ServerPrefixes

    if not os.path.exists("Backups"):
        os.makedirs("Backups")
    BackupFile = os.path.join("Backups", "Prefixes.json")
    if os.path.exists(BackupFile):
        print("Restoring Custom Prefixes")
        with open(BackupFile, "r") as PrefixBackup:
            ServerPrefixes = json.load(PrefixBackup)

        NewServerPrefixDict = {}
        for OldKey in ServerPrefixes.keys():
            try:
                NewKey = int(OldKey)
                NewServerPrefixDict[NewKey] = ServerPrefixes[OldKey]
            except ValueError:
                print("Error in adapting Prefixes from JSON.")
        ServerPrefixes = NewServerPrefixDict


    print("Setting up Guild Profiles")
    for guild in bot.guilds:
        ServerProfiles[guild.id] = Guild_Profile(guild)
        print("\nThis server has ID and Name: ")
        print(guild.id)
        print(guild.name)

        BackupFileName = str(guild.id) + ".json"
        BackupFolder = os.path.join("HeraldBackups", BackupFileName)
        if os.path.exists(BackupFolder):
            with open(BackupFolder, 'r') as backup:
                ServerProfiles[guild.id].HeraldSongs = json.load(backup)
                print("Retreived Herald Profiles!")

                # We've already downloaded the Herald videos, so we just need to load the dictionaries

            newHeraldProfileDict = {}
            for OldKey in ServerProfiles[guild.id].HeraldSongs.keys():
                try:
                    NewKey = int(OldKey)
                    newHeraldProfileDict[NewKey] = ServerProfiles[guild.id].HeraldSongs[OldKey]
                except ValueError:
                    print("Error in adapting HeraldSongs from JSON.")
            ServerProfiles[guild.id].HeraldSongs = newHeraldProfileDict
    print("SETUP ENDED.  READY TO OPERATE.")


@bot.event
async def on_guild_join(guild):
    print("This server has ID and Name: ")
    print(guild.id)
    print(guild.name + "\n")
    ServerProfiles[guild.id] = Guild_Profile(guild)


# endregion

class Guild_Profile():
    def __init__(self, Guild):
        self.Guild = Guild
        self.HeraldSongs = dict()  # Initialize a dictionary for Herald profiles
        self.MusicQueue = queue.Queue()
        self.successful_join = False
        self.vc = None
        self.playingNOW = False
        self.PlayingEvent = asyncio.Event()
        self.CurrentSong = (None, None)  # (Filepath, URL)
        self.SkippingNow = False  # Note that this variable is only used for the purposes of JumpTo
        self.CurrentMusicStartTime = None # This is used to track the current timestamp of the song playing so that it can resume properly when interrupted by Herald
        self.InterruptedByHerald = False
        self.LazyDeleteSongs = []  # A list of songs to delete when the bot leaves voice that were put on hold due to Herald.

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


# region Help Setup
class MyHelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        e = discord.Embed(color=discord.Color.blurple(), description='')
        for page in self.paginator.pages:
            e.description += page
        await destination.send(embed=e)


bot.help_command = MyHelpCommand()


# endregion

# region Herald Functionality
@bot.event
async def on_voice_state_update(user, before, after):
    """Triggers Herald Theme.  Awaits user to join voice and plays audio clip if user has set one."""
    global FFmpegPCMAudio_FilePath
    global ServerProfiles
    if before.channel is None and after.channel is not None:
        # User has connected to a VoiceChannel
        channel = after.channel
        ThisServerProfile = ServerProfiles[after.channel.guild.id]

        if user.id in ThisServerProfile.HeraldSongs.keys():
            print("Heralding " + user.name + " on Guild " + ThisServerProfile.Guild.name)
            channel = user.voice.channel  # Note the channel to play music in
            RestoreTime = ThisServerProfile.CurrentMusicStartTime

            if ThisServerProfile.playingNOW:
                ThisServerProfile.InterruptedByHerald = True
                RestoreTime = int(time.time() - ThisServerProfile.CurrentMusicStartTime)
                print(RestoreTime)
                ThisServerProfile.vc.pause()  # Pauses music if any is playing currently.

            if not ThisServerProfile.successful_join: #ThisServerProfile.vc.is_connected():
                ThisServerProfile.vc = await channel.connect()
                ThisServerProfile.successful_join = True
            ThisServerProfile.vc.play(FFmpegPCMAudio(executable=FFmpegPCMAudio_FilePath, source=ThisServerProfile.HeraldSongs[user.id][1], before_options="-ss " + ThisServerProfile.HeraldSongs[user.id][3]), after=lambda e: print("Done playing for user " + user.name + "."))

            start = time.time()  # Check the starttime so we can only play for 15s or less.
            elapsed = 0

            while elapsed < ThisServerProfile.HeraldSongs[user.id][5]:  # Sleep while the video plays for 15 Seconds
                print("Waiting for Herald to finish...", elapsed)
                elapsed = time.time() - start
                await asyncio.sleep(1)

            print("Done Waiting")
            print("PlayingNow: ", ThisServerProfile.playingNOW)

            if ThisServerProfile.playingNOW:
                print("Resuming Music")
                Timestamp = CalculateTimeStamp(RestoreTime)
                ThisServerProfile.vc.play(FFmpegPCMAudio(executable=FFmpegPCMAudio_FilePath, source=ThisServerProfile.CurrentSong[0], before_options="-ss " + Timestamp), after=lambda e: ThisServerProfile.PlayingEvent.set())
            else:
                #await HeraldVC.disconnect()
                await ThisServerProfile.vc.disconnect()

                # Reset Server variables
                ThisServerProfile.successful_join = False
                ThisServerProfile.vc = None
                ThisServerProfile.PlayingNOW = False
                ThisServerProfile.PlayingEvent.clear()
    elif before.channel is not None and after.channel is None:
            # Indicates someone leaving voice chat.
            if user.id == 1035362429758083072: # This is the bot's id.  So, if the bot disconnects from voice
                ThisServerProfile = ServerProfiles[before.channel.guild.id]
                try:
                    if ThisServerProfile.vc:
                        ThisServerProfile.vc.stop()
                except Exception as e:
                    print("Error: Failed to properly stop voice when disconnecting.")
                    print(e)
                for filepath in ThisServerProfile.LazyDeleteSongs:  # delete all lazy delete songs
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print("Error: Failed to remove song with filepath: " + filepath)
                        print(e)



@bot.command(name="HeraldSet",
             description="Sets up a herald bot profile.  Provide a short YouTube URL to play every time you join voice.  "
                         "Provide a url and timestamp (in seconds) and a 15 second clip starting from that timestamp will be saved.")
async def HeraldSet(ctx, url, StartTime=0):
    """Sets the Herald Theme for the user."""
    print("HeraldSet Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    # Initialize global variables
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    HeraldUser = ctx.author
    HeraldKey = HeraldUser.id  # Takes the user's id.  This will be used as the key for the dictionary.
    if HeraldKey in ThisServerProfile.HeraldSongs:
        os.remove(ThisServerProfile.HeraldSongs[HeraldKey][1])

    EndTime = StartTime  # Initialize variable EndTime
    HeraldVideo = YouTube(str(url))
    if HeraldVideo.length - StartTime < 15:  # Check if the video clip is less than 15 seconds
        EndTime = HeraldVideo.length  # If it is, allow the Herald Clip to be less than 15 seconds
    elif HeraldVideo.length - StartTime >= 15:  # If the remainder of the video after the timestamp is greater than 15 seconds,
        EndTime = StartTime + 15  # Just take the 15 seconds after the provided timestamp.  If no timestamp was given, this is just the first 15 seconds.

    try:
        file = downloadHERALD(url, HeraldKey)  # Returns tuple containing the filepath and file name
    except:
        await ctx.send("ERROR: Herald Theme download failed.")
        print("ERROR: Herald Theme download failed.")

    StartTimeStampCode = CalculateTimeStamp(StartTime)
    print("Starting Timestamp for user " + HeraldUser.name + ":", StartTimeStampCode)
    EndTimeStampCode = CalculateTimeStamp(EndTime)
    print("Starting Timestamp for user " + HeraldUser.name + ":", EndTimeStampCode)
    ThisServerProfile.HeraldSongs[HeraldKey] = (url, file[0], file[1], StartTimeStampCode, EndTimeStampCode, EndTime)  # Stores the file as a tuple: URL (backup), filepath, file name, StartTime, EndTime

    userMentionTag = HeraldUser.mention
    print("Success!  Herald theme for " + HeraldUser.name + " has been changed to: " +
          ThisServerProfile.HeraldSongs[HeraldKey][2])
    await ctx.send(userMentionTag + "Success!  Your Herald theme has been changed to: " + ThisServerProfile.HeraldSongs[HeraldKey][2])

    if not os.path.exists("HeraldBackups"):
        os.makedirs("HeraldBackups")
    BackupFile = "HeraldBackups/" + str(ThisServerProfile.Guild.id) + ".json"
    with open(BackupFile, "w") as outfile:
        json.dump(ThisServerProfile.HeraldSongs, outfile)


@bot.command(name="HeraldTheme", description="Returns the user's herald theme.")
async def HeraldTheme(ctx):
    """Returns the user's Herald Theme if one is set."""
    print("HeraldTheme Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    try:
        print("HeraldTheme Printout for Server" + ThisServerProfile.Guild.name + "\n", ThisServerProfile.HeraldSongs)
        HeraldID = ctx.author.id
        userMentionTag = ctx.author.mention
        if HeraldID in ThisServerProfile.HeraldSongs.keys():
            print("Herald theme for user " + ctx.author.name + " is: " + ThisServerProfile.HeraldSongs[HeraldID][2] + ", LINK: " + ThisServerProfile.HeraldSongs[HeraldID][0])
            await ctx.send(userMentionTag + "Your Herald theme is: " + ThisServerProfile.HeraldSongs[HeraldID][2] + ", LINK: " + ThisServerProfile.HeraldSongs[HeraldID][0])
        else:
            await ctx.send(
                userMentionTag + "You do not have a Herald theme set.  To set one use the HeraldSet command, along with a link to a short youtube video.")

    except Exception as e:
        await ctx.send("ERROR: HERALD THEME CHECK FAILED.")
        print("ERROR: HERALD THEME CHECK FAILED.")
        print(e)


# endregion

# region Generic Commands
@bot.command(name="Hello", description="Tags the user to greet them.")
async def hello(ctx):
    """Tags the user to greet them."""
    await ctx.send(ctx.author.mention + " hello!")


@bot.command(name="prefix_change", description="Changes the command prefix to the given parameter")
async def pref_change(ctx, new_pref):
    """Changes the command prefix to the given parameter"""
    print("Prefix Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)

    global ServerPrefixes
    ServerPrefixes[ctx.message.guild.id] = new_pref  # Creates/changes entry in dictionary
    await ctx.send("Prefix has been set to: " + new_pref)

    with open("Backups/Prefixes.json", "w") as outfile:  # Backs up the custom prefix
        json.dump(ServerPrefixes, outfile)


# endregion

# region Voice_Channel_Commands

@bot.command(name="JumpTo", description="If a song is currently playing, jumps to the given timestamp (in seconds).")
async def JumpTo(ctx, TimeStamp):
    """If a song is currently playing, jumps to the given timestamp."""
    global FFmpegPCMAudio_FilePath
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]

    print("Received JumpTo Command (" + TimeStamp + "s)")
    if ThisServerProfile.playingNOW:
        CurrentVideo = YouTube(ThisServerProfile.CurrentSong[1])  # Make sure this is actually url
        if int(TimeStamp) < CurrentVideo.length:
            SongToDelete = ThisServerProfile.CurrentSong[0]  # Note down the filepath so we can remove it.
            ThisServerProfile.SkippingNow = True
            ThisServerProfile.vc.stop()

            JumpVideoEvent = asyncio.Event()
            STARTTimestampCode = CalculateTimeStamp(int(TimeStamp))  # Convert timestamp code to version FFMPEG can use.  Easier to do this than sanitize timestamp inputs.
            waiter_task = asyncio.create_task(WaitAndDelete(JumpVideoEvent, SongToDelete, ThisServerProfile))

            ThisServerProfile.vc.play(FFmpegPCMAudio(executable=FFmpegPCMAudio_FilePath,source=ThisServerProfile.CurrentSong[0], before_options="-ss " + STARTTimestampCode), after=lambda e: JumpVideoEvent.set())

            await ctx.send("Skipped to " + STARTTimestampCode)
            print("Skipped to " + STARTTimestampCode)
            await waiter_task  # Wait until the waiter task is finished - which is when the music stops playing
            os.remove(SongToDelete)  # Delete the file ourselves since we told the waiter task not to delete while we're fastforwarding
            ThisServerProfile.SkippingNow = False

        else:
            await ctx.send(ctx.author.mention + " Invalid timestamp.  Please select a timestamp less than the videolength (in seconds).")
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can Fastforward or JumpTo through it!")


@bot.command(name="Join", description="Summons Unicron to join the voice channel.")
async def join(ctx):
    """Bot joins the voice channel."""
    global ServerProfiles

    print("Join Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]

    try:  # Checks if user is in a voice channel
        channel = ctx.author.voice.channel
        if not ThisServerProfile.successful_join:
            ThisServerProfile.vc = await channel.connect()
            ThisServerProfile.successful_join = True
    except:
        await ctx.send("User must be in a voice channel")

    if ThisServerProfile.vc is None or not ThisServerProfile.vc.is_connected():  # Check that we aren't already in a voice channel before attempting to connect
        print("\n\nJoining Guild: " + ctx.message.guild.name)
        await ctx.author.voice.channel.connect()
        ThisServerProfile.vc = discord.utils.get(client.voice_clients, guild=ctx.guild)
    return ThisServerProfile.vc


@bot.command(name="Leave", description="Commands the bot to leave the voice channel.")
async def leave(ctx):
    """Bot leaves the voice channel."""
    print("Leave Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    print(str(ThisServerProfile))

    if ThisServerProfile.playingNOW:  # Clear the queue out and stop the player.
        ThisServerProfile.MusicQueue = queue.Queue()
        if ThisServerProfile.vc:
            ThisServerProfile.vc.stop()

    # Then we will disconnect.
    await ThisServerProfile.vc.disconnect()

    # Reset Server variables
    ThisServerProfile.successful_join = False
    ThisServerProfile.vc = None
    ThisServerProfile.PlayingNOW = False
    ThisServerProfile.PlayingEvent.clear()


@bot.command(name="Pause", description="Pauses the audio, if any if playing.  Resume with Resume.")
async def pause(ctx):
    """Pauses the audio, if any if playing.  Resume with Resume."""
    print("Pause Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        # Pause audio
        ThisServerProfile.vc.pause()
    else:
        # Don't try to pause if not playing now.  We'll have a null pointer exception.
        await ctx.send(ctx.author.mention + " No audio playing.  Play something with command: Play")


@bot.command(name="Resume", description="Resumes the audio if any was playing or paused.")
async def resume(ctx):
    """Resumes the audio if any was playing or paused."""
    print("Resume Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        ThisServerProfile.vc.resume()  # resumes music if any was playing.
    else:
        await ctx.send(
            ctx.author.mention + " No audio playing.  Maybe you meant to play something with command: Play")


@bot.command(name="Skip", description="Skips the current song if any was playing.")
async def skip_song(ctx):
    """Skips the current song if any was playing."""
    print("Skip Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        ThisServerProfile.vc.stop()  # Stop, trigger waiter event to end and then proceed to next song (if one is there)
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can skip it!")


@bot.command(name="Stop", description="Stops playing all audio and clears the queue.")
async def stop_playing(ctx):
    """Stops playing all audio and clears the queue."""
    print("Stop Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    if ThisServerProfile.playingNOW:
        ThisServerProfile.MusicQueue = queue.Queue()  # Clear out the queue
        ThisServerProfile.vc.stop()  # Stop.  Nothing will play after since the queue is empty now.
        ThisServerProfile.playingNOW = False  # Show that we aren't playing now.
    else:
        print("Music not playing.  Current queue size: " + str(ThisServerProfile.MusicQueue.qsize()))
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can stop it!")


@bot.command(name="Play", description="Adds a video to the music queue.")
async def PlayEnqueue(ctx, url):
    """Command that user interacts with.  Adds urls to a music queue which are popped and played by PlayQ"""
    print("Enqueue Command Received from user " + ctx.message.author.name + " on Guild " + ctx.message.guild.name)
    # Initialize global variables
    global ServerProfiles
    try:  # Check that the command sender is in a voice channel.  If not, ignore the command.
        UserVoiceChannel = ctx.author.voice.channel  # Looks up the user channel.  If this fails (except), then we throw out the command since the user is not in voice.
    except Exception as e:
        await ctx.send("An exception occurred.  This may be because the user is not in the voice channel.")
        print("An exception occurred.  This may be because the user is not in the voice channel.")
        print(e)
        return  # Throw out this command

    try:
        ThisServerProfile = ServerProfiles[ctx.message.guild.id]

        if "list" in str(url):  # Check if we're dealing with a pleylist
            p = Playlist(str(url))
            await  ctx.send("Queueing up a playlist..." + p.title)
            print("Queueing up a playlist..." + p.title)
            for vid in p.video_urls:
                ThisServerProfile.MusicQueue.put((ctx, vid))
                print("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize()))
        else:  # Not dealing with a playlist.  Just a single video.
            ThisServerProfile.MusicQueue.put((ctx, url))  # Add song to queue
            vid = YouTube(str(url))
            await ctx.send("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize()))
            print("Enqueued: " + str(vid.title) + " at position " + str(ThisServerProfile.MusicQueue.qsize()))

        if not ThisServerProfile.successful_join:
            # If we aren't already in voice for this server, then we can join
            await join(ctx)

        if not ThisServerProfile.playingNOW:  # Check if we're playing right now.  If we are, no need to start up the queue.
            await PlayQ(ctx, ThisServerProfile.vc)
    except Exception as e:
        await ctx.send("An exception occurred.  Plese check the log for more details.")
        print("An exception occurred.... See Below: ")
        print(e)


async def PlayQ(ctx, voice):
    """Command used to play the queue of songs/videos enqueued with PlayEnqueue."""
    print("Running PlayQueue " + " on Guild " + ctx.message.guild.name)
    # Global variable declarations
    global ServerProfiles
    ThisServerProfile = ServerProfiles[ctx.message.guild.id]
    ThisServerProfile.PlayingEvent.set()
    ThisServerProfile.playingNOW = True

    while True:
        if not ThisServerProfile.InterruptedByHerald:  # If we're interrupted by Herald, we want to keep looping without doing anything until the flag is lowered.
            ThisServerProfile.PlayingEvent.clear()
            Current = ThisServerProfile.MusicQueue.get()  # Pop a song from the queue
            file = download(Current[1])  # Download the song that was linked.
            CurrentSongFilePath = file[0]  # Take the file path for the downloaded song.
            ThisServerProfile.CurrentSong = (CurrentSongFilePath, Current[1])
            waiter_task = asyncio.create_task(WaitAndDelete(ThisServerProfile.PlayingEvent, CurrentSongFilePath, ThisServerProfile))

            ThisServerProfile.vc.play(FFmpegPCMAudio(executable=FFmpegPCMAudio_FilePath, source=CurrentSongFilePath), after=lambda e: ThisServerProfile.PlayingEvent.set())
            await ctx.send("NOW PLAYING: " + file[1])
            print("NOW PLAYING: " + file[1] + " On Guild " + ctx.message.guild.name)
            ThisServerProfile.CurrentMusicStartTime = time.time()
            await waiter_task  # Wait until the waiter task is finished - which is when the music stops playing
            while ThisServerProfile.SkippingNow:
                await asyncio.sleep(1)

            if ThisServerProfile.MusicQueue.qsize() == 0:  # When our queue is empty, we can leave since our work here is done.
                ThisServerProfile.playingNOW = False
                await leave(ctx)
                break


# endregion

# region Helper Functions
def CalculateTimeStamp(Seconds):
    """Returns a timestamp in format HH:MM:SS.MS, given a timestamp in seconds (integer)."""
    if Seconds < 362439:  # This is the number of seconds equal to 99:99:99.00 in HH:MM:SS.MS
        Hours = Seconds // 3600
        Minutes = (Seconds % 3600) // 60
        Seconds = Seconds % 60
        TimeStampCode = str(Hours) + ":" + str(Minutes) + ":" + str(Seconds) + ".00"
        return TimeStampCode
    else:
        return "99:99:99.00"


async def WaitAndDelete(event, FilePath, ServerProfile):
    """Takes an event and waits until it finishes before deleting the provided filepath."""
    await event.wait()
    print("Finished Playing.")
    print("Skipping now: ", ServerProfile.SkippingNow)
    if not ServerProfile.SkippingNow:
        if not ServerProfile.InterruptedByHerald:
            print("Deleting file and moving to next song:")
            os.remove(FilePath)
        else:
            print("Interrupted by Herald, so adding song to lazy delete list to be cleared when leaving voice channel.")
            ServerProfile.LazyDeleteSongs.append(FilePath)
            ServerProfile.InterruptedByHerald = False

#@asyncio.to_thread
#async def HeraldRestore(guildID):
def HeraldRestore(guildID):
    for userID in ServerProfiles[guildID].HeraldSongs.keys():
        HeraldProfile = ServerProfiles[guildID].HeraldSongs[userID]
        try:
            File = downloadHERALD(HeraldProfile[0], userID)
            HeraldProfile[1] = File[0]
            HeraldProfile[2] = File[1]
        except Exception as e:
            print("ERROR in Restoring Herald Profile for USER ID: ", userID)
            print(e)



# endregion

"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
if __name__ == "__main__":
    print("About to run")
    print("Looking for Herald Backup files")
    for filename in os.listdir("HeraldBackups"):
        #Download herald themes before connecting to discord
        f = os.path.join("HeraldBackups", filename)
        # checking if it is a file
        if os.path.isfile(f) and os.path.splitext(f)[1] == ".json":
            print(f)

            with open(f, 'r') as backup:
                print("File opened")
                TempHeraldRestoration = json.load(backup)
                print("Attempting to download")
                try:
                    for userID in TempHeraldRestoration.keys():
                        print("Downloading " + TempHeraldRestoration[userID][2] + " for user with ID: " + userID)
                        print(TempHeraldRestoration[userID][0])
                        file = downloadHERALD(TempHeraldRestoration[userID][0], userID)
                        print("Download successful.")
                        TempHeraldRestoration[userID][1] = file[0]

                except Exception as e:
                    print("Error with opening HeraldBackup JSON")
                    print(e)

            with open(f, 'w') as backup:
                try:
                    # Write updated file locations to the backup JSON file
                    json.dump(TempHeraldRestoration, backup)  # Write new file locations to the backup
                except Exception as e:
                    print("Error with writing to HeraldBackup JSON")
                    print(e)

    bot.run(token)
