import asyncio
import itertools
import json
import os

import discord
from discord.ext import commands, tasks

TOKEN = os.environ.get("TOKEN") or open("token.txt").read().strip()
CONFIG_FILE = "config.json"
CONFIG_FILE = "config.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="r.", intents=intents, help_command=None)

# ---------- rotating status (har 10 sec) ----------
STATUSES = [
    "Join our server | link in bio",
    "Helping in server | link in bio",
    "Roblox Event Server 🪔",
    "Watching all members 👀",
]
status_cycle = itertools.cycle(STATUSES)


@tasks.loop(seconds=10)
async def rotate_status():
    try:
        await bot.change_presence(
            activity=discord.CustomActivity(name=next(status_cycle))
        )
    except Exception:
        pass


# ---------- config ----------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)


# ---------- member counter ----------
async def update_stats(guild, create_if_missing=False):
    cfg = load_config()
    channel = None
    cid = cfg.get(str(guild.id))
    if cid:
        channel = guild.get_channel(cid)

    name = f"🪔 Members: {guild.member_count}"

    if channel is None:
        if not create_if_missing:
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, connect=False
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, connect=True, manage_channels=True
            ),
        }
        channel = await guild.create_voice_channel(
            name, overwrites=overwrites, position=0
        )
        cfg[str(guild.id)] = channel.id
        save_config(cfg)
    elif channel.name != name:
        await channel.edit(name=name)


@bot.event
async def on_ready():
    print(f"Online: {bot.user}")
    if not rotate_status.is_running():
        rotate_status.start()
    for guild in bot.guilds:
        await update_stats(guild)


@bot.event
async def on_member_join(member):
    await update_stats(member.guild)


@bot.event
async def on_member_remove(member):
    await update_stats(member.guild)


# ---------- commands (prefix: r.) ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await update_stats(ctx.guild, create_if_missing=True)
    await ctx.send("✅ Member counter channel created.")


@bot.command()
@commands.has_permissions(administrator=True)
async def dm(ctx, user: discord.Member, *, message: str):
    try:
        await user.send(message)
        await ctx.send(f"✅ DM sent to {user}.")
    except discord.Forbidden:
        await ctx.send(f"❌ {user} has DMs closed.")


@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message: str):
    await ctx.send("📨 Sending...")
    sent = failed = 0
    for m in ctx.guild.members:
        if m.bot:
            continue
        try:
            await m.send(message)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        await asyncio.sleep(1.5)
    await ctx.send(f"✅ Sent: {sent} | ❌ Failed: {failed}")


@bot.command()
@commands.has_permissions(administrator=True)
async def dmrole(ctx, role: discord.Role, *, message: str):
    sent = failed = 0
    for m in role.members:
        if m.bot:
            continue
        try:
            await m.send(message)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        await asyncio.sleep(1.5)
    await ctx.send(f"✅ Sent: {sent} | ❌ Failed: {failed}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Admins only.")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send(f"❌ Wrong usage of `r.{ctx.command}`.")
    elif not isinstance(error, commands.CommandNotFound):
        raise error


bot.run(TOKEN)
