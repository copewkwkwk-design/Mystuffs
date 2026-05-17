import asyncio
import os
import discord
from discord.ext import commands

# --- CONFIGURATION SETTINGS ---
# We use os.environ.get to safely pull the token from Railway's settings
TOKEN = os.environ.get("DISCORD_TOKEN")
PARTNERSHIP_ROLE_NAME = "rep"  
AD_CHANNEL_ID = 1409925659979022448  
TICKET_BOT_ID = 557628352828014614  
# ------------------------------

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user.name}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Detect when Ticket Tool speaks inside a ticket channel
    if message.author.id == TICKET_BOT_ID and "ticket" in message.channel.name.lower():
        ctx_channel = message.channel
        
        # FIND THE HUMAN OWNER OF THE TICKET VIA MENTIONS
        target_user = None
        if message.mentions:
            for user in message.mentions:
                if not user.bot:
                    target_user = user
                    break

        # Fallback to scanning channel members if mention detection fails
        if not target_user:
            for member in ctx_channel.members:
                if member.bot:
                    continue
                perms = ctx_channel.permissions_for(member)
                if perms.view_channel:
                    target_user = member
                    break

        if not target_user:
            return

        # GREET THE USER
        await ctx_channel.send(
            f"Hi, {target_user.mention} I'll be assisting your ticket. Please lend us your **Advertisement** here.\n"
            "-# reply to this message with your advertisement  on to continue. If not, the bot will ignore your message."
        )

        def check_ad(m):
            return m.author == target_user and m.channel == ctx_channel

        # LOOP TO VALIDATE THE ADVERTISEMENT
        user_ad_msg = None
        while True:
            try:
                user_ad_msg = await bot.wait_for("message", check=check_ad, timeout=600)
            except asyncio.TimeoutError:
                return

            msg_content = user_ad_msg.content.lower()

            # Check if the message contains a link
            if "http://" in msg_content or "https://" in msg_content or "discord.gg" in msg_content:
                break
            else:
                await user_ad_msg.reply("this is not an **Ad**")

        # POSTING THE ADVERTISEMENT
        ad_channel = bot.get_channel(AD_CHANNEL_ID)
        if ad_channel:
            await user_ad_msg.reply(f"Posting your **Ad** on {ad_channel.mention}")
            await ad_channel.send(user_ad_msg.content)
            await ad_channel.send(f"Partnership with {target_user.mention}!")
        else:
            print("Error: Ad channel not found.")

        # GIVE THE "rep" ROLE
        member_in_guild = message.guild.get_member(target_user.id)
        if member_in_guild:
            role = discord.utils.get(message.guild.roles, name=PARTNERSHIP_ROLE_NAME)
            if role:
                try:
                    await member_in_guild.add_roles(role)
                except discord.Forbidden:
                    print("Error: Bot role needs to be higher in the server settings.")
            else:
                print(f"Error: Role '{PARTNERSHIP_ROLE_NAME}' not found.")

        # CLOSING LOOP (opo / wala pa po)
        while True:
            await ctx_channel.send(
                "posted na po ba?\n-# only reply with a \"opo / wala pa po\" "
            )

            def check_confirmation(m):
                return (
                    m.author == target_user
                    and m.channel == ctx_channel
                    and m.content.lower().strip() in ["opo", "wala pa po"]
                )

            try:
                conf_msg = await bot.wait_for("message", check=check_confirmation, timeout=600)
                user_response = conf_msg.content.lower().strip()

                if user_response == "opo":
                    await ctx_channel.send(
                        "Thank you so much for partnering with us! Closing ticket..."
                    )
                    await asyncio.sleep(3)
                    await ctx_channel.delete()
                    break

                elif user_response == "wala pa po":
                    await ctx_channel.send("ahh, take your time po")

            except asyncio.TimeoutError:
                break

    await bot.process_commands(message)

if TOKEN:
    bot.run(TOKEN)
else:
    print("CRITICAL ERROR: DISCORD_TOKEN environment variable is missing!")
