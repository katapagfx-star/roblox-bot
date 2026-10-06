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
def make_embed(message, ctx, title):
    embed = discord.Embed(
        title=title,
        description=message[:4000],
        color=0xFF0000,
    )
    embed.set_footer(text=f"From {ctx.guild.name}")
    return embed


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
    if channel is None:
        for vc in guild.voice_channels:
            if vc.name.startswith("🪔 Members:"):
                channel = vc
                break

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
        await user.send(embed=make_embed(message, ctx, "📩 Message"))
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
            await m.send(embed=make_embed(message, ctx, "📢 Announcement"))
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
            await m.send(embed=make_embed(message, ctx, "📢 Announcement"))
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        await asyncio.sleep(1.5)
    await ctx.send(f"✅ Sent: {sent} | ❌ Failed: {failed}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tumhare paas is command ki permission nahi hai.")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send(f"❌ Wrong usage of `r.{ctx.command}`.")
    elif not isinstance(error, commands.CommandNotFound):
        raise error


# ---- MODERATION ----
from datetime import timedelta


def parse_duration(text):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        return int(text[:-1]) * units[text[-1].lower()]
    except (ValueError, KeyError, IndexError):
        return None


def can_act(ctx, member):
    if member == ctx.author or member == ctx.guild.owner or member == ctx.guild.me:
        return False
    if ctx.author != ctx.guild.owner and member.top_role >= ctx.author.top_role:
        return False
    return member.top_role < ctx.guild.me.top_role


NO_ACT = "❌ Is member par action nahi ho sakta (role upar hai ya khud/owner)."
NO_BOT_PERM = "❌ Bot ke paas permission nahi hai (bot ka role upar rakho)."


@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if not 1 <= amount <= 500:
        return await ctx.send("❌ Amount 1 se 500 ke beech do.")
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🧹 {len(deleted) - 1} messages delete kiye.", delete_after=4)
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not can_act(ctx, member):
        return await ctx.send(NO_ACT)
    try:
        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(f"👢 {member} ko kick kiya. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not can_act(ctx, member):
        return await ctx.send(NO_ACT)
    try:
        await member.ban(reason=f"{ctx.author}: {reason}")
        await ctx.send(f"🔨 {member} ko ban kiya. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        await ctx.guild.unban(discord.Object(id=user_id))
        await ctx.send(f"✅ User `{user_id}` unban ho gaya.")
    except discord.NotFound:
        await ctx.send("❌ Ye user banned nahi hai.")
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str, *, reason: str = "No reason"):
    secs = parse_duration(duration)
    if secs is None or not 1 <= secs <= 28 * 86400:
        return await ctx.send("❌ Time aise do: 30s, 10m, 2h, 1d (max 28d).")
    if not can_act(ctx, member):
        return await ctx.send(NO_ACT)
    try:
        await member.timeout(timedelta(seconds=secs), reason=f"{ctx.author}: {reason}")
        await ctx.send(f"🔇 {member} ko {duration} ke liye mute kiya. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 {member} unmute ho gaya.")
    except discord.Forbidden:
        await ctx.send(NO_BOT_PERM)


@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    ow = ctx.channel.overwrites_for(ctx.guild.default_role)
    ow.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send("🔒 Channel lock ho gaya.")


@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    ow = ctx.channel.overwrites_for(ctx.guild.default_role)
    ow.send_messages = None
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send("🔓 Channel unlock ho gaya.")


@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    if not 0 <= seconds <= 21600:
        return await ctx.send("❌ 0 se 21600 seconds ke beech do.")
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"🐢 Slowmode: {seconds}s" if seconds else "✅ Slowmode off.")


@bot.command(name="help")
async def help_cmd(ctx):
    await ctx.send(
        "**Commands (prefix: r.)**\n"
        "`r.purge <n>` `r.kick @u [reason]` `r.ban @u [reason]` `r.unban <id>`\n"
        "`r.mute @u <10m> [reason]` `r.unmute @u` `r.lock` `r.unlock` `r.slowmode <s>`\n"
        "`r.dm @u <msg>` `r.dmall <msg>` `r.dmrole @role <msg>` `r.setup`\n"
        "Slash: `/ping`"
    )


@bot.tree.command(name="ping", description="Bot ki latency check karo")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")


_synced = False


async def sync_slash():
    global _synced
    if not _synced:
        await bot.tree.sync()
        _synced = True


bot.add_listener(sync_slash, "on_ready")
# ---- END MODERATION ----


bot.run(TOKEN)
