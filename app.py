import discord
from discord.ext import commands
import shelve
import logging
import sys
from flask import Flask
from threading import Thread
import os
from dotenv import load_dotenv

ROLE = "DF"
MIN_INVITES = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Copied from docs
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

load_dotenv()
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

DATA_FILE = "invite_data.db"

def load_data():
    with shelve.open(DATA_FILE) as db:
        return dict(db) if db else {}

def save_data(data):
    with shelve.open(DATA_FILE) as db:
        db.clear()
        for key, value in data.items():
            db[key] = value

invite_data = load_data()
invite_cache = {}

@bot.event
async def on_ready():
    logging.info(f"✅ Bot is online as {bot.user.name}")

    # Cache copied from stackoverflow
    for guild in bot.guilds:
        try:
            invite_cache[guild.id] = await guild.invites()
            logging.info(f"📌 Cached invites for {guild.name} ({guild.id})")
        except Exception as e:
            logging.error(f"Invite caching error: {e}")

@bot.command()
async def ping(ctx):
    """Check the bot's latency"""
    latency = round(bot.latency * 1000)  # latency in ms
    await ctx.send(f"🏓 Pong! Latency is {latency}ms")
    logging.info(f"🔍 Ping command triggered. Latency: {latency}ms")

@bot.command()
async def invites(ctx):
    """Check your invite count"""
    user_id = str(ctx.author.id)
    count = invite_data.get(user_id, {}).get("total", 0)
    await ctx.send(f"📊 You've invited {count} members!")
    logging.info(f"🔍 {ctx.author.name} checked invites: {count}")

# hithala daapu feature eka :)
@bot.command()
async def all_invite_details(ctx):
    # Check if the command is used in a server
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    # Get the Member object
    member = ctx.guild.get_member(ctx.author.id)
    if not member:
        await ctx.send("❌ Could not fetch your member details. Try again.")
        return

    # Check if user has role 'X' or is 'thevindu_senanayake'
    if ROLE not in [role.name for role in member.roles] and member.name != "thevindu_senanayake":
        await ctx.send("❌ You don't have the required role to access invite details.")
        return

    # Fetch invite details
    guild = ctx.guild
    details = []
    for invite in invite_cache.get(guild.id, []):
        inviter = invite.inviter
        total_uses = invite.uses
        details.append(f"📩 Invite Code: `{invite.code}`, Inviter: **{inviter.name}**, Uses: `{total_uses}`")

    if details:
        await ctx.send("\n".join(details))
        logging.info(f"🔍 {ctx.author.name} requested invite details.")
    else:
        await ctx.send("❌ No invite details available.")
        logging.warning(f"⚠️ {ctx.author.name} attempted to request invite details, but no data was found.")

@bot.command()
async def invite_details(ctx):
    # Check if the command is used in a server
    if ctx.guild is None:
        await ctx.send("❌ This command can only be used in a server, not in DMs.")
        return

    # Get the Member object
    member = ctx.guild.get_member(ctx.author.id)
    if not member:
        await ctx.send("❌ Could not fetch your member details. Try again.")
        return

    # Check if user has role 'X' or is 'thevindu_senanayake'
    if ROLE not in [role.name for role in member.roles] and member.name != "thevindu_senanayake":
        await ctx.send("❌ You don't have the required role to access invite details.")
        return

    # Load invite data from database
    invite_data = load_data()

    if not invite_data or len({user_id: data for user_id, data in invite_data.items() if data["total"] > 0}) == 0:
        await ctx.send("❌ No invite data available.")
        return

    # Sort users by total invites in descending order
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1]["total"], reverse=True)

    # Format the leaderboard output
    leaderboard = "**📊 Invite Leaderboard**\n"
    for i, (user_id, data) in enumerate(sorted_invites, start=1):
        user = ctx.guild.get_member(int(user_id))
        username = user.name if user else f"User-{user_id}"
        leaderboard += f"**{i}. {username} - {data['total']} invites**\n"

    await ctx.send(leaderboard)
    logging.info(f"🔍 {ctx.author.name} requested invite leaderboard.")



@bot.event
async def on_member_join(member):
    guild = member.guild
    new_invites = await guild.invites()
    old_invites = invite_cache.get(guild.id, [])
    inviter = None

    for new_invite in new_invites:
        for old_invite in old_invites:
            if new_invite.code == old_invite.code and new_invite.uses > old_invite.uses:
                inviter = guild.get_member(new_invite.inviter.id)
                if not inviter:
                   continue

    invite_cache[guild.id] = new_invites  # Update the cache

    if inviter:
        inviter_id = str(inviter.id)
        if inviter_id not in invite_data:
            invite_data[inviter_id] = {"total": 0, "users": []}
        invite_data[inviter_id]["total"] += 1
        invite_data[inviter_id]["users"].append(str(member.id))
        save_data(invite_data)

        logging.info(f"✅ {inviter.name} invited {member.name}! Total invites: {invite_data[inviter_id]['total']}")

        if invite_data[inviter_id]["total"] >= MIN_INVITES:
            role = discord.utils.get(guild.roles, name="VIP")
            if role and role not in inviter.roles:
                await inviter.add_roles(role)
                await guild.system_channel.send(f"🎉 {inviter.mention} earned VIP")
                logging.info(f"🏆 {inviter.name} awarded VIP role!")

@bot.event
async def on_member_remove(member):
    guild = member.guild
    member_id = str(member.id)

    inviter_id = None
    for uid, data in invite_data.items():
        if "users" in data and member_id in data["users"]:
            inviter_id = uid
            break

    if inviter_id:
        invite_data[inviter_id]["total"] = max(0, invite_data[inviter_id]["total"] - 1)
        invite_data[inviter_id]["users"].remove(member_id)
        save_data(invite_data)

        inviter = guild.get_member(int(inviter_id))
        logging.info(f"❌ {member.name} left or was kicked. {inviter.name}'s invite count: {invite_data[inviter_id]['total']}")

        if inviter:
            role = discord.utils.get(guild.roles, name="VIP")
            if role and role in inviter.roles and invite_data[inviter_id]["total"] < MIN_INVITES:
                await inviter.remove_roles(role)
                logging.info(f"⚠️ {inviter.name} lost VIP role")

keep_alive()
bot.run(DISCORD_TOKEN)
