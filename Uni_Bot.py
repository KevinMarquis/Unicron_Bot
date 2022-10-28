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
intents = discord.Intents.all()
# intents.message_content = True
token = 'MTAzNTM2MjQyOTc1ODA4MzA3Mg.G8JInH.FwQS46hqeYwMkl28qWOzKgWsY66n_elx-W1Xpg'
default_prefix = "!"
prefix = default_prefix  # We will keep prefix/user data as instance data for now - this will be changed to be per server
bot = commands.Bot(command_prefix='$', intents=intents)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


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
    prefix = new_pref
    bot.command_prefix = prefix
    await ctx.send("Prefix has been set to: " + prefix)


"""STARTUP"""
# Assume client refers to a discord.Client subclass...
# Suppress the default configuration since we have our own
# client.run(token, log_handler=None)
bot.run(token)
