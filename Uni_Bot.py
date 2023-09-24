import discord
import logging.handlers
from discord.ext import commands
from discord import FFmpegPCMAudio
from pytube import Playlist, YouTube
import asyncio
from VidDownloader import download, download_herald
import queue
import Token
import os
import json
import time
import Unicron_Image

# region Constants
INTENTS = discord.Intents.default()  # Set bot permissions.
INTENTS.message_content = True  # This may need to be commented out for linux <^
TOKEN = Token.HiddenToken  # Pull the token from another file.
SERVER_PROFILES = dict()  # Initializes a dictionary with server ids as keys to another dictionary.
SERVER_PREFIXES = dict()  # Initializes a dictionary with server ids as keys to the command prefix for that server.
CWD = os.getcwd()
ACTIVITY = discord.Activity(name="Consuming the multiverse", type=discord.ActivityType.custom, state="Consuming the Multiverse")

# WINDOWS:
# You may need to change these filepaths
FFMPEG_PCM_AUDIO_FILEPATH = os.path.join(CWD, "ffmpeg-2022-10-27-git-00b03331a0-full_build", "bin", "ffmpeg.exe")
# RASBIAN/LINUX:
# FFMPEG_PCM_AUDIO_FILEPATH = os.path.join("/usr", "bin", "ffmpeg")
# endregion


# region Util
def get_prefix(client, message):
    """Returns the prefix for the bot to use.

    If the server has a prefix set in its profile, returns that value.
    Otherwise, defaults to "!".  This function is called only by the discord.py API.

    Args:
        client: Client object for the bot.
        message: Automatically filled in by the discord API.

    Returns:
        A string containing the prefix for the bot to use for the target channel.
    """
    global SERVER_PREFIXES
    if message.guild.id in SERVER_PREFIXES:  # Checks for a custom prefix
        return SERVER_PREFIXES[message.guild.id]
    else:
        return "!"  # Default Prefix


# region Music Utils
async def download_song(guild_id, url):
    """Downloads a song to be played.

    Downloads a song and writes the song filepath to the server profile object.

    Args:
        guild_id: ID number corresponding to the guild being accessed.
        url: URL of the song to be downloaded and played on this guild.
    """
    ThisServerProfile = SERVER_PROFILES[guild_id]
    ThisServerProfile.CurrentSongFile = await download(url)


def calculate_time_stamp(seconds):
    """Converts a timestamp in seconds to the format HH:MM:SS.MS.

    Args:
        seconds: an integer containing the timestamp in seconds.

    Returns:
        Timestamp string in the desired format.
    """
    if seconds < 362439:  # This is the number of seconds equal to 99:99:99.00 in HH:MM:SS.MS
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        timestamp_code = str(hours) + ":" + str(minutes) + ":" + str(seconds) + ".00"
        return timestamp_code
    else:
        return "99:99:99.00"


async def wait_and_delete(event, filepath, server_profile):
    """Deletes a song file once it has finished playing in voicechat.

    Uses an asyncio event object to be called after a song finishes playing
    Should only be called with asyncio create_task.

    Args:
        event: Asyncio event object that is tied to a task.
        filepath: File path for the song currently playing.
        server_profile: Server profile object for the server currently being accessed.
    """
    await event.wait()
    bot_logger.debug("Finished Playing.")
    bot_logger.debug(f"Skipping now: {server_profile.SkippingNow}")
    if not server_profile.SkippingNow:
        if not server_profile.InterruptedByHerald:
            bot_logger.debug("Deleting file and moving to next song:")
            os.remove(filepath)
        else:
            bot_logger.debug("Interrupted by Herald. Adding song to lazy delete list to be cleared when leaving VC.")
            server_profile.LazyDeleteSongs.append(filepath)
            server_profile.InterruptedByHerald = False
# endregion
# endregion


# region ERROR LOGGING
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('{asctime} {levelname} {name}: {message}', dt_fmt, style='{')

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)
bot_logger = logging.getLogger('unicron')
bot_logger.setLevel(logging.DEBUG)
vid_dl_logger = logging.getLogger('download')
vid_dl_logger.setLevel(logging.DEBUG)


# Send output to Console (Warning+ only)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(formatter)

# Create Handler to output log to files (everything)
file_handler = logging.handlers.TimedRotatingFileHandler(filename='Unicron_Testing.log',
                                                         encoding='utf-8',
                                                         when='midnight',
                                                         backupCount=7,
                                                         utc=True)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

bot_logger.addHandler(console_handler)
bot_logger.addHandler(file_handler)
discord_logger.addHandler(console_handler)
discord_logger.addHandler(file_handler)
vid_dl_logger.addHandler(console_handler)
vid_dl_logger.addHandler(file_handler)
bot_logger.propogate = False
# endregion

bot = commands.Bot(command_prefix=get_prefix, intents=INTENTS, case_insensitive=True, activity = ACTIVITY)
client = discord.Client(intents=INTENTS)


# region Join Setup
@bot.event
async def on_ready():
    """Triggers when the bot is online and restores server profiles.

    Opens up server JSON files and extracts settings, including Herald profiles
    and server settings.
    """

    bot_logger.info('We have logged in as %s', bot.user)

    global SERVER_PROFILES
    global SERVER_PREFIXES

    if not os.path.exists("Backups"):
        os.makedirs("Backups")
    backup_file = os.path.join("Backups", "Prefixes.json")
    if os.path.exists(backup_file):
        bot_logger.debug("Restoring Custom Prefixes")
        with open(backup_file, "r") as PrefixBackup:
            SERVER_PREFIXES = json.load(PrefixBackup)

        NewServerPrefixDict = {}
        for OldKey in SERVER_PREFIXES.keys():
            try:
                NewKey = int(OldKey)
                NewServerPrefixDict[NewKey] = SERVER_PREFIXES[OldKey]
            except ValueError:
                bot_logger.error("Error in adapting Prefixes from JSON.")
        SERVER_PREFIXES = NewServerPrefixDict

    bot_logger.info("Setting up Guild Profiles")
    for guild in bot.guilds:
        SERVER_PROFILES[guild.id] = Guild_Profile(guild)
        bot_logger.debug("This server has ID %s and Name: %s", guild.id, guild.name)

        BackupFileName = str(guild.id) + ".json"
        BackupFolder = os.path.join("HeraldBackups", BackupFileName)
        if os.path.exists(BackupFolder):
            with open(BackupFolder, 'r') as backup:
                SERVER_PROFILES[guild.id].HeraldSongs = json.load(backup)
                bot_logger.debug("Retreived Herald Profiles!")

                # We've already downloaded the Herald videos, so we just need to load the dictionaries

            newHeraldProfileDict = {}
            for OldKey in SERVER_PROFILES[guild.id].HeraldSongs.keys():
                try:
                    NewKey = int(OldKey)
                    newHeraldProfileDict[NewKey] = SERVER_PROFILES[guild.id].HeraldSongs[OldKey]
                except ValueError:
                    bot_logger.error("Error in adapting HeraldSongs from JSON.")
            SERVER_PROFILES[guild.id].HeraldSongs = newHeraldProfileDict
    bot_logger.info("SETUP ENDED. READY TO OPERATE.")
    print(Unicron_Image.UNICRON_IMAGE)
    print("---------UNICRON IS ONLINE---------")


@bot.event
async def on_guild_join(guild):
    """Event that triggers when the bot joins a new guild.

    Writes out data to the log.
    """
    bot_logger.info(f"Joined Server with ID {guild.id} and name {guild.name}")
    SERVER_PROFILES[guild.id] = Guild_Profile(guild)


# endregion

class Guild_Profile():
    def __init__(self, guild):
        """Initializes a new Guild Profile object.

        Args:
            guild: Discord API Guild object (for a server).

        Returns:
            None
        """
        self.Guild = guild
        self.HeraldSongs = dict()  # Initialize a dictionary for Herald profiles
        self.MusicQueue = queue.Queue()
        self.successful_join = False
        self.vc = None
        self.playingNOW = False
        self.PlayingEvent = asyncio.Event()
        self.CurrentSong = (None, None)  # (Filepath, URL)
        self.SkippingNow = False  # Note that this variable is only used for the purposes of JumpTo
        self.CurrentMusicStartTime = None  # Used to track the current timestamp of the song playing so that it can
                                           # resume properly when interrupted by Herald
        self.InterruptedByHerald = False
        self.LazyDeleteSongs = []  # List of songs to delete when the bot leaves vc that were put on hold due to Herald.
        self.CurrentSongFile = None
        self.Game = dict()  # Dictionary for the game scores

    def __str__(self):
        """Creates a readable string format to read the Guild Profile Data.

        This function is used solely for debug/logging.

        Returns:
            String representation of the Guild Profile.
        """
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


# region Herald Functionality
@bot.event
async def on_voice_state_update(user, before, after):
    """Bot event that triggers the Herald theme to play upon joining voice chat.

    Function triggered as an event that will play the herald theme in chat.
    Whenever a user that has created a herald profile on the server joins
    the voice chat, Unicron will join the server, play their short Herald
    theme and leave the chat. This function should not be called directly.
    Instead, it should exclusively be called by the discord API.

    Args:
        user: The user object for the user whose voice status was updated.
        before: The voice channel the user had previously been in (if any).
        after: The voice channel the user is now in (if any).
    """
    global FFMPEG_PCM_AUDIO_FILEPATH
    global SERVER_PROFILES
    if before.channel is None and after.channel is not None:
        # User has connected to a VoiceChannel
        channel = after.channel
        target_serv_prof = SERVER_PROFILES[after.channel.guild.id]

        if user.id in target_serv_prof.HeraldSongs.keys():
            bot_logger.info(f"Heralding {user.name} on Guild {target_serv_prof.Guild.name}")
            channel = user.voice.channel  # Note the channel to play music in
            RestoreTime = target_serv_prof.CurrentMusicStartTime

            if target_serv_prof.playingNOW:  # Pauses music if any is playing currently.
                target_serv_prof.InterruptedByHerald = True
                RestoreTime = int(time.time() - target_serv_prof.CurrentMusicStartTime)
                bot_logger.info(f"Herald Restore Time: {RestoreTime}")
                target_serv_prof.vc.pause()

            if not target_serv_prof.successful_join:
                target_serv_prof.vc = await channel.connect()
                target_serv_prof.successful_join = True

            target_serv_prof.vc.play(FFmpegPCMAudio(executable=FFMPEG_PCM_AUDIO_FILEPATH,
                                                    source=target_serv_prof.HeraldSongs[user.id][1],
                                                    before_options="-ss " + target_serv_prof.HeraldSongs[user.id][3]),
                                     after=lambda e: bot_logger.info(f"Done playing for user {user.name}."))

            start = time.time()  # Check the starttime so we can only play for 15s or less.
            elapsed = 0

            while elapsed < target_serv_prof.HeraldSongs[user.id][5]:  # Sleep while the video plays for 15 Seconds
                bot_logger.debug(f"Waiting for Herald to finish...{elapsed}")
                elapsed = time.time() - start
                await asyncio.sleep(1)

            bot_logger.debug("Done Waiting for Herald")
            target_serv_prof.vc.pause()
            bot_logger.debug(f"PlayingNow: {target_serv_prof.playingNOW}")

            if target_serv_prof.playingNOW:
                bot_logger.info("Resuming Music")
                Timestamp = calculate_time_stamp(RestoreTime)
                target_serv_prof.vc.play(FFmpegPCMAudio(executable=FFMPEG_PCM_AUDIO_FILEPATH,
                                                        source=target_serv_prof.CurrentSong[0],
                                                        before_options="-ss " + Timestamp),
                                         after=lambda e: target_serv_prof.PlayingEvent.set())
            else:
                await target_serv_prof.vc.disconnect()

                # Reset Server variables
                target_serv_prof.successful_join = False
                target_serv_prof.vc = None
                target_serv_prof.PlayingNOW = False
                target_serv_prof.PlayingEvent.clear()
    elif before.channel is not None and after.channel is None:
        # Indicates someone leaving voice chat.
        if user.id == 1035362429758083072:  # This is the bot's id. => if the bot disconnects from voice
            target_serv_prof = SERVER_PROFILES[before.channel.guild.id]
            try:
                if target_serv_prof.vc:
                    target_serv_prof.vc.stop()
            except Exception as e:
                bot_logger.error("Error: Failed to properly stop voice when disconnecting.")
                bot_logger.debug(e)
            for filepath in target_serv_prof.LazyDeleteSongs:  # delete all lazy delete songs
                try:
                    bot_logger.debug("Clearing Lazy Delete List.")
                    os.remove(filepath)
                except Exception as e:
                    bot_logger.warning("Error: Failed to remove song with filepath: " + filepath)
                    bot_logger.debug(e)


@bot.command(name="HeraldSet",
             description="Sets up a herald profile. Provide a short YouTube URL to play every time you join voice.\n"
                         "Provide a url and timestamp (in seconds) and a 15s clip starting from the time will be saved")
async def herald_set(ctx, url, start_time=0):
    """This function sets a Herald Theme for the user.

    User-accessible command that sets the herald theme for the user.
    If the user previously had a herald theme, the old theme is overwritten.
    After saving the audio file, the JSON file is written to in order to backup the
    new Herald theme, in the event that the bot resets.

    Args:
        ctx: Discord API context object for the caller
        url: URL to the YouTube video that is to be set as the HeraldTheme.
        start_time: Integer. Time in seconds for the theme to start at.
    """
    bot_logger.debug(f"HeraldSet CMD received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    # Initialize global variables
    global SERVER_PROFILES
    this_srv_prof = SERVER_PROFILES[ctx.message.guild.id]
    hrld_usr = ctx.author
    hrld_key = hrld_usr.id  # Takes the user's id.  This will be used as the key for the dictionary.
    if hrld_key in this_srv_prof.HeraldSongs:
        os.remove(this_srv_prof.HeraldSongs[hrld_key][1])

    end_time = start_time  # Initialize variable EndTime
    hrld_vid = YouTube(str(url))
    if hrld_vid.length - start_time < 15:  # Check if the video clip is less than 15 seconds
        end_time = hrld_vid.length  # If it is, allow the Herald Clip to be less than 15 seconds
    elif hrld_vid.length - start_time >= 15:  # If the remainder of the video after the timestamp is greater than 15s,
        end_time = start_time + 15  # If no timestamp was given, this is just the first 15 seconds.

    try:
        file = download_herald(url, hrld_key)  # Returns tuple containing the filepath and file name
    except Exception as e:
        await ctx.send("ERROR: Herald Theme download failed.")
        bot_logger.error(f"ERROR: Herald Theme download failed for user {ctx.message.author.name}.")
        bot_logger.debug(e)

    start_timestamp_code = calculate_time_stamp(start_time)
    bot_logger.info(f"Starting Timestamp for user {hrld_usr.name}: {start_timestamp_code}")
    end_timestamp_code = calculate_time_stamp(end_time)
    bot_logger.info(f"Ending Timestamp for user {hrld_usr.name}: {end_timestamp_code}")
    # Stores the file as a tuple: URL (backup), filepath, file name, StartTime, EndTime
    this_srv_prof.HeraldSongs[hrld_key] = (url, file[0], file[1], start_timestamp_code, end_timestamp_code, end_time)

    usr_mention = hrld_usr.mention
    herald_theme = this_srv_prof.HeraldSongs[hrld_key][2]
    await ctx.send(f"{usr_mention} Success! Your Herald theme has been changed to: {herald_theme}")
    bot_logger.info(f"{usr_mention} Herald theme has been changed to: {herald_theme}")

    # Back up new herald theme
    if not os.path.exists("HeraldBackups"):
        os.makedirs("HeraldBackups")
    backup_file = "HeraldBackups/" + str(this_srv_prof.Guild.id) + ".json"
    with open(backup_file, "w") as outfile:
        json.dump(this_srv_prof.HeraldSongs, outfile)


@bot.command(name="HeraldTheme", description="Returns the user's herald theme.")
async def herald_theme(ctx):
    """Replies with the user's Herald theme if one is set.

    User-accessible command that replies with the HeraldTheme they set (if any).

    Args:
        ctx: Discord API context object for the sender of the command.
    """
    bot_logger.info(f"HeraldTheme CMD Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_srv_prof = SERVER_PROFILES[ctx.message.guild.id]
    try:
        bot_logger.info(f"HeraldThemes for Server {this_srv_prof.Guild.name}: {this_srv_prof.HeraldSongs}")
        hrld_id = ctx.author.id
        usr_mention = ctx.author.mention
        if hrld_id in this_srv_prof.HeraldSongs.keys():
            await ctx.send(usr_mention + "Your Herald theme is: " + this_srv_prof.HeraldSongs[hrld_id][2] +
                           ", LINK: " + this_srv_prof.HeraldSongs[hrld_id][0])
            bot_logger.info(f"Released Herald Theme for user {ctx.author.name}.")

        else:
            await ctx.send(usr_mention + ("You do not have a Herald theme set. To set one, use the HeraldSet command, "
                                          "along with a link to a short YouTube video."))

    except Exception as e:
        await ctx.send("ERROR: HERALD THEME CHECK FAILED.")
        bot_logger.error("ERROR: HERALD THEME CHECK FAILED.")
        bot_logger.debug(e)
# endregion


# region Generic Commands
@bot.command(name="Hello", description="Tags the user to greet them.")
async def hello(ctx):
    """Command that greets a user in discord text chat.

    User-accessible command that messages a user a hello message.
    This command is primarily used for verifying that the bot is online.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    await ctx.send(ctx.author.mention + " hello!")
    bot_logger.info(f"Greeted user {ctx.author} with a hello message")


@bot.command(name="prefix_change", description="Changes the command prefix to the given parameter")
async def pref_change(ctx, new_pref):
    """Command that changes the command prefix for the server.

    User-accessible command that changes the command prefix for the current server context.

    Args:
        ctx: Discord.py context object for the message to be sent in.
        new_pref: String containing the new prefix to be prepended before all commands.
    """
    bot_logger.debug(f"Prefix Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")

    global SERVER_PREFIXES
    SERVER_PREFIXES[ctx.message.guild.id] = new_pref  # Creates/changes entry in dictionary
    await ctx.send("Prefix has been set to: " + new_pref)
    bot_logger.info(f"Prefix for guild with ID {ctx.message.guild.id} has been set to: {new_pref}")

    with open("Backups/Prefixes.json", "w") as outfile:  # Backs up the custom prefix
        json.dump(SERVER_PREFIXES, outfile)
        bot_logger.debug("Backed up new custom prefix.")
# endregion


# region Voice_Channel_Commands
@bot.command(name="Jump", description="If a song is currently playing, jumps to the given timestamp (in seconds).")
async def jump_to(ctx, timestamp):
    """Command that fast forwards or rewinds the currently playing song to a given timestamp.

    User-accessible command that will set the timestamp for the currently playing song to the user provided
    time in seconds.

    Args:
        ctx: Discord.py context object for the message to be sent in.
        timestamp: Integer containing the timestamp in seconds.
    """
    global FFMPEG_PCM_AUDIO_FILEPATH
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]

    bot_logger.debug("Received JumpTo Command (" + timestamp + "s)")
    if this_server_profile.playingNOW:
        current_video = YouTube(this_server_profile.CurrentSong[1])  # Make sure this is actually url
        if int(timestamp) < current_video.length:
            song_to_delete = this_server_profile.CurrentSong[0]  # Note down the filepath so we can remove it.
            this_server_profile.SkippingNow = True
            this_server_profile.vc.stop()

            jump_video_event = asyncio.Event()
            start_timestamp_code = calculate_time_stamp(int(timestamp))  # Convert timestamp to version FFMPEG can use.
            waiter_task = asyncio.create_task(wait_and_delete(jump_video_event, song_to_delete, this_server_profile))

            this_server_profile.vc.play(FFmpegPCMAudio(executable=FFMPEG_PCM_AUDIO_FILEPATH,
                                                       source=this_server_profile.CurrentSong[0],
                                                       before_options="-ss " + start_timestamp_code),
                                        after=lambda e: jump_video_event.set())

            await ctx.send("Skipped to " + start_timestamp_code)
            bot_logger.info("Skipped to " + start_timestamp_code)
            await waiter_task  # Wait until the waiter task is finished - which is when the music stops playing
            os.remove(song_to_delete)  # Delete the file since we told the waiter task not to delete when we fastforward
            this_server_profile.SkippingNow = False

        else:
            await ctx.send(ctx.author.mention + " Invalid timestamp. Please select a valid time (in seconds).")
            bot_logger.debug("Received jump Command with invalid timestamp.")
    else:
        await ctx.send(ctx.author.mention + " No audio playing. You'll need to play something before you can use Jump.")
        bot_logger.debug("Received jump command, but no audio was playing in the voice channel.")


@bot.command(name="Join", description="Summons Unicron to join the voice channel.")
async def join(ctx):
    """Command that summons the bot to the voice channel the user is currently in.

    User-accessible command that summons the bot to the current voice channel.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    global SERVER_PROFILES

    bot_logger.debug(f"Join Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]

    try:  # Checks if user is in a voice channel
        channel = ctx.author.voice.channel
        if not this_server_profile.successful_join:
            this_server_profile.vc = await channel.connect()
            this_server_profile.successful_join = True
    except Exception as e:
        bot_logger.warning("Join Error: ", e)
        await ctx.send("User must be in a voice channel")

    if this_server_profile.vc is None or not this_server_profile.vc.is_connected():  # Check that we aren't in vc
        bot_logger.info(f"Joining Guild {ctx.message.guild.name}...")
        await ctx.author.voice.channel.connect()
        this_server_profile.vc = discord.utils.get(client.voice_clients, guild=ctx.guild)
        bot_logger.info("Successfully joined target Guild VC.")
    return this_server_profile.vc


@bot.command(name="Leave", description="Commands the bot to leave the voice channel.")
async def leave(ctx):
    """Command that forces the bot to leave the voice channel.

    User-accessible command that forces the bot to leave the current voice channel
    in this server.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    bot_logger.debug(f"Leave Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    bot_logger.debug(str(this_server_profile))

    if this_server_profile.playingNOW:  # Clear the queue out and stop the player.
        this_server_profile.MusicQueue = queue.Queue()
        if this_server_profile.vc:
            this_server_profile.vc.stop()

    # Then we will disconnect.
    await this_server_profile.vc.disconnect()
    bot_logger.info(f"Successfully left VC on guild {ctx.message.guild.name}")

    # Reset Server variables
    this_server_profile.successful_join = False
    this_server_profile.vc = None
    this_server_profile.PlayingNOW = False
    this_server_profile.PlayingEvent.clear()


@bot.command(name="Pause", description="Pauses the audio, if any if playing. Resume with Resume.")
async def pause(ctx):
    """Command that pauses the audio playing in the current voice channel, if any.

    User-accessible command that pauses the audio playing in the current voice channel
    if any is playing.  If no audio is playing, does nothing.  Paused audio can be resumed
    with the resume command.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    bot_logger.debug(f"Pause Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    if this_server_profile.playingNOW:
        # Pause audio
        this_server_profile.vc.pause()
        bot_logger.info(f"Audio on guild {ctx.message.guild.name} has been paused successfully.")
    else:
        # Don't try to pause if not playing now.  We'll have a null pointer exception.
        await ctx.send(ctx.author.mention + " No audio playing.  Play something with command: Play")
        bot_logger.debug("Pause command received but no audio is playing.")


@bot.command(name="Resume", description="Resumes the audio if any was playing or paused.")
async def resume(ctx):
    """Command that plays the audio that was paused in the current voice channel, if any.

    User-accessible command that plays the audio that is paused in the current voice channel, if any.
    If no audio is paused, does nothing.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    bot_logger.debug(f"Resume Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    if this_server_profile.playingNOW:
        this_server_profile.vc.resume()  # resumes music if any was playing.
        bot_logger.info(f"Audio on guild {ctx.message.guild.name} has been resumed successfully.")
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  Maybe you meant to play something with command: Play")
        bot_logger.debug("Resume command received but no audio is paused.")


@bot.command(name="Skip", description="Skips the current song if any was playing.")
async def skip_song(ctx):
    """Command that skips the audio track playing in the current voice channel, if any.

    User-accessible command that skips the currently playing audio track in the voice channel
    and moves to the next song in the queue.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    bot_logger.debug(f"Skip Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    if this_server_profile.playingNOW:
        this_server_profile.vc.stop()  # Stop, trigger waiter event to end, then proceed to next song (if one is there)
        bot_logger.info(f"Audio on guild {ctx.message.guild.name} has been skipped successfully.")
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can skip it!")
        bot_logger.debug("Skip command received but no audio is playing.")


@bot.command(name="Stop", description="Stops playing all audio and clears the queue.")
async def stop_playing(ctx):
    """Command that stops the audio playing in the current voice channel, if any.

    User-accessible command that stops any audo playing in the current voice channel
    and clears the queue.

    Args:
        ctx: Discord.py context object for the message to be sent in.
    """
    bot_logger.debug(f"Stop Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    if this_server_profile.playingNOW:
        this_server_profile.MusicQueue = queue.Queue()  # Clear out the queue
        this_server_profile.vc.stop()  # Stop.  Nothing will play after since the queue is empty now.
        this_server_profile.playingNOW = False  # Show that we aren't playing now.
        bot_logger.info(f"Audio on guild {ctx.message.guild.name} has been stopped successfully.")
    else:
        await ctx.send(ctx.author.mention + " No audio playing.  You'll need to play something before you can stop it!")
        bot_logger.debug("Stop command received but no audio is playing.")
        bot_logger.debug(f"Current Queue Size: {this_server_profile.MusicQueue.qsize()}")


@bot.command(name="Play", description="Adds a video to the music queue.")
async def play_enq(ctx, url):
    """Command that adds an audio track the the queue, to be played in the current voice channel.

    User-accessible command that adds a track with a given URL to the audio queue.  It will
    be played in the current voice channel.

    Args:
        ctx: Discord.py context object for the message to be sent in.
        url: YouTube URL to the song that shall be played.
    """
    bot_logger.debug(f"Enqueue Command Received from user {ctx.message.author.name} on Guild {ctx.message.guild.name}")
    # Initialize global variables
    global SERVER_PROFILES
    try:  # Check that the command sender is in a voice channel.  If not, ignore the command.
        user_voice_chnl = ctx.author.voice.channel  # Looks up the user channel.  If this fails the user is not in vc.
    except Exception as e:
        await ctx.send("An exception occurred.  This may be because the user is not in the voice channel.")
        bot_logger.warning("An exception occurred in enqueue. This may be because the user isn't in the voice channel.")
        bot_logger.debug(e)
        return  # Throw out this command

    try:
        this_server_profile = SERVER_PROFILES[ctx.message.guild.id]

        if "list" in str(url):  # Check if we're dealing with a pleylist
            p = Playlist(str(url))
            await ctx.send("Queueing up a playlist..." + p.title)
            bot_logger.debug("Queueing up a playlist..." + p.title)
            for vid in p.video_urls:
                this_server_profile.MusicQueue.put((ctx, vid))
                bot_logger.info(f"Enqueued: {str(vid.title)} at position {this_server_profile.MusicQueue.qsize()}")
        else:  # Not dealing with a playlist.  Just a single video.
            this_server_profile.MusicQueue.put((ctx, url))  # Add song to queue
            vid = YouTube(str(url))
            await ctx.send(f"Enqueued: {str(vid.title)} at position {str(this_server_profile.MusicQueue.qsize())}.")
            bot_logger.info(f"Enqueued: {str(vid.title)} at position {str(this_server_profile.MusicQueue.qsize())}.")

        if not this_server_profile.successful_join:
            # If we aren't already in voice for this server, then we can join
            await join(ctx)

        if not this_server_profile.playingNOW:  # If we are playing, no need to start up the queue.
            await play_deq(ctx, this_server_profile.vc)
    except Exception as e:
        await ctx.send("An exception occurred.  Plese check the log for more details.")
        bot_logger.warning("An exception occured while queueuing a video or playlist.  See the log for more info.")
        bot_logger.debug(e)


async def play_deq(ctx, voice):
    """Plays the enqueued audio tracks in the voice channel.

    This is a non-user-accessible function that plays any audio tracks that have been enqueued
    using play_enq.  This function is looped in until the queue has been emptied.

    Args:
        ctx: Discord.py context object for the message to be sent in.
        voice: Voice client for the server context that music is to be played in.
            The value is not used, but is instead used to ensure a voice client
            exists.
    """
    bot_logger.debug(f"Running PlayQueue on Guild {ctx.message.guild.name}")

    # Global variable declarations
    global SERVER_PROFILES
    this_server_profile = SERVER_PROFILES[ctx.message.guild.id]
    this_server_profile.PlayingEvent.set()
    this_server_profile.playingNOW = True

    while True:
        if not this_server_profile.InterruptedByHerald:  # If we're interrupted by Herald, we want to keep looping, w/o
                                                         # doing anything until the flag is lowered.
            this_server_profile.PlayingEvent.clear()
            curr = this_server_profile.MusicQueue.get()  # Pop a song from the queue

            await download_song(ctx.message.guild.id, curr[1])
            file = this_server_profile.CurrentSongFile
            curr_song_filepath = file[0]  # Take the file path for the downloaded song.
            this_server_profile.CurrentSong = (curr_song_filepath, curr[1])
            waiter_task = asyncio.create_task(wait_and_delete(this_server_profile.PlayingEvent,
                                                              curr_song_filepath,
                                                              this_server_profile))
            this_server_profile.vc.play(FFmpegPCMAudio(executable=FFMPEG_PCM_AUDIO_FILEPATH, source=curr_song_filepath),
                                        after=lambda e: this_server_profile.PlayingEvent.set())
            await ctx.send("NOW PLAYING: " + file[1])
            bot_logger.debug("NOW PLAYING: " + file[1] + " On Guild " + ctx.message.guild.name)
            this_server_profile.CurrentMusicStartTime = time.time()
            await waiter_task  # Wait until the waiter task is finished - which is when the music stops playing
            while this_server_profile.SkippingNow:
                await asyncio.sleep(1)

            if this_server_profile.MusicQueue.qsize() == 0:  # When our queue is empty, we can leave vc
                this_server_profile.playingNOW = False
                await leave(ctx)
                break


# endregion

# region Quiz Mode
@bot.command(name="Button", description="Click the button!")
async def button(ctx):
    role = discord.utils.find(lambda r: r.name == 'Game Master', ctx.message.guild.roles)
    if role in ctx.message.author.roles:
        view = QuizButtons("Option 1", "Option 2")
        # button = discord.ui.Button(label="Click me")
        # view.add_item(button)
        await ctx.send(view = view)
    else:
        await ctx.send("You must be a game master to summon the buttons!")

@bot.command(name="GameReset", description="Resets the game scores.")
async def game_reset(ctx):
    role = discord.utils.find(lambda r: r.name == 'Game Master', ctx.message.guild.roles)
    if role in ctx.message.author.roles:
        SERVER_PROFILES[ctx.message.guild.id].Game = dict()
        ctx.send("Game scores have been reset")
    else:
        await ctx.send("You must be a game master to reset game scores!")

@bot.command(name="GameStart", description="Starts a new game.  Allows participants to join in.")
async def game_start(ctx):
    role = discord.utils.find(lambda r: r.name == 'Game Master', ctx.message.guild.roles)
    if role in ctx.message.author.roles:
        SERVER_PROFILES[ctx.message.guild.id].Game = dict()

        view = QuizStart(SERVER_PROFILES[ctx.message.guild.id].Game)
        await ctx.send(content = "Join the game!", view = view)
        
    else:
        await ctx.send("You must be a game master to reset game scores!")


@bot.command(name="Quiz", description="Click the button!")
async def quiz_mode(ctx):
    #if # role doesnt exist
    if "Game Master" not in ctx.guild.roles:
        await ctx.send("No Game Master role exists.  Creating role. "
                 "Please assign this role to yourself to control the quiz.")
        await ctx.guild.create_role(name="Game Master")
    
    view = QuizButtons("Option 1", "Option 2")
    # button = discord.ui.Button(label="Click me")
    # view.add_item(button)
    await ctx.send(view = view)


class QuizStart(discord.ui.View):
    
    def __init__(self, game_dict = None):
        super().__init__(timeout=600)
        self.game = game_dict
    

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game[interaction.user.id] = 0
        await interaction.response.send_message(f"{interaction.user.mention} You joined the game!")
        #self.stop()
    
    @discord.ui.button(label="End Joining", style=discord.ButtonStyle.red)
    async def end_button(self, interraction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.find(lambda r: r.name == 'Game Master', interraction.guild.roles)
        if role in interraction.user.roles:
            await interraction.response.send_message("Game Joining Ended!")
            self.stop()
        else:
            await interraction.response.send_message("You must be a game master to end joining!")


class QuizButtons(discord.ui.View):

    def __init__(self, button1_name = "A", button2_name = "B"):
        self.button1_name = button1_name
        self.button2_name = button2_name
        super().__init__(timeout=600)
        self.add_buttons()
    
    @discord.ui.button(label="Hello", style=discord.ButtonStyle.green)
    async def hello_button(self, interraction: discord.Interaction, button: discord.ui.Button):
        await interraction.response.send_message("World")
        #self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interraction: discord.Interaction, button: discord.ui.Button):
        await interraction.response.send_message("Cancel")
        self.stop()
    
    def add_buttons(self):
        button_one = discord.ui.Button(label=self.button1_name)
        
        async def buttonexample(interaction: discord.Interaction):
            await interaction.response.send_message("You pressed the button! " + self.button1_name)
        
        button_one.callback = buttonexample
        self.add_item(button_one)

        button_two = discord.ui.Button(label=self.button2_name)
        async def buttonexample2(interaction: discord.Interaction):
            await interaction.response.send_message("You pressed the button! " + self.button2_name)
        
        button_two.callback = buttonexample2
        self.add_item(button_two)
    


# endregion

"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
bot.run(TOKEN, log_level=logging.DEBUG, log_handler=file_handler)
