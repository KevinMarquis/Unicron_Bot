import discord
import logging
import logging.handlers
from discord.ext import commands

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
token = ''  #TODO
default_prefix = "!"
prefix = default_prefix  # We will keep prefix/user data as instance data for now - this will be changed to be per server
bot = commands.Bot(command_prefix='$')

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

''' - May not need this
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')
'''

"""FUNCTIONS"""
@bot.command()
async def help(ctx):
    message_release = "------HELP------\n"
    message_release += prefix + "help - Prints out all commands\n"
    message_release += prefix + "prefix _ - Sets the prefix to be the inputted character(s)\n"
    ctx.send(message_release)

@bot.command()
def pref_change(ctx, new_pref):
    """Changes the bot's command prefix to the given parameter"""
    nonlocal prefix
    prefix = new_pref
    bot.command_prefix = prefix
    ctx.send("Prefix has been set to: " + prefix)


"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
client.run(token, log_handler=None)


