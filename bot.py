import asyncio
import discord
from discord.ext import commands, tasks
import re
import os

# ==========================================
# CONFIGURATION & CREDENTIALS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

STAFF_ROLE_ID = 1409944574541037678          
REP_ROLE_ID = 1421777773286129734            
PARTNERSHIP_CHANNEL_ID = 1409925659979022448   
OUR_AD_CHANNEL_ID = 1409922038507769886  # ⚠️ Replace with the actual channel ID where your ad is stored!

INVITE_REGEX = r"(?:https?://)?(?:www\.)?(?:discord\.gg/|discord(?:app)?\.com/invite/)[a-zA-Z0-9-]+"

# ==========================================
# BOT INITIALIZATION
# ==========================================
intents = discord.Intents.default()
intents.message_content = True  
intents.guilds = True  
intents.members = True  

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# RICH PRESENCE LOOP
# ==========================================
status_toggle = 0

@tasks.loop(seconds=15)
async def update_presence():
    global status_toggle
    
    # Safely calculate total members across all servers the bot is in
    total_members = sum(guild.member_count for guild in bot.guilds if guild.member_count)
    
    if status_toggle == 0:
        activity = discord.Streaming(
            name=f"Watching /rougekin with {total_members} members", 
            url="https://twitch.tv/discord"
        )
    else:
        activity = discord.Streaming(
            name="Watching Made by kupes", 
            url="https://twitch.tv/discord"
        )
        
    await bot.change_presence(status=discord.Status.online, activity=activity)
    status_toggle = (status_toggle + 1) % 2

@update_presence.before_loop
async def before_update_presence():
    await bot.wait_until_ready()

# ==========================================
# WORKFLOW UTILITIES
# ==========================================
async def close_ticket_channel(channel: discord.TextChannel, final_message: str):
    await channel.send(final_message)
    await asyncio.sleep(5)
    try:
        await channel.delete()
    except discord.Forbidden:
        await channel.send("⚠️ I don't have permission to delete this channel.")

async def handle_partnership_workflow(bot: commands.Bot, channel: discord.TextChannel, user_target: discord.Member):
    welcome_msg = (
        f"{user_target.mention}, please drop your server's ad text below:\n"
        "*(Note: Your ad MUST contain a valid Discord Server link!)*"
    )
    await channel.send(welcome_msg)

    def check_ad(m):
        return m.author == user_target and m.channel == channel

    ad_message = None

    # Wait indefinitely for a valid ad with a link
    while True:
        msg = await bot.wait_for('message', check=check_ad, timeout=None)
        
        if re.search(INVITE_REGEX, msg.content):
            ad_message = msg
            break
        else:
            error_msg = (
                f"⚠️ **Invalid ad!** {user_target.mention}, your message must contain a valid Discord invite link. "
                "External links or text-only messages are not allowed.\n\n"
                "Please post your ad again:"
            )
            await channel.send(error_msg)

    # Post to your alliance logging channel
    ps_channel = bot.get_channel(PARTNERSHIP_CHANNEL_ID)
    if ps_channel:
        await ps_channel.send(content=f"**New Alliance!**\n\n{ad_message.content}\n\nPartnershiped with {user_target.mention}")
    
    # Point them to your server's ad
    await channel.send(f"Awesome! You can find our **ad** to copy in <#{OUR_AD_CHANNEL_ID}>.")
    
    # Send the final confirmation message with the "Posted" button
    prompt_msg = f"Your **ad** has been posted, {user_target.mention}! Have you posted our server's advertisement as well?"
    await channel.send(content=prompt_msg, view=PartnershipConfirmView(target_user=user_target))

# ==========================================
# INTERACTIVE UI VIEWS
# ==========================================
class PartnershipConfirmView(discord.ui.View):
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=None)
        self.target_user = target_user

    @discord.ui.button(label="Posted", style=discord.ButtonStyle.success, custom_id="partnership_confirm:posted")
    async def posted_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("Only the ticket creator can click this!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        rep_role = interaction.guild.get_role(REP_ROLE_ID)
        if rep_role:
            try:
                await self.target_user.add_roles(rep_role)
                await interaction.channel.send(f"🎉 {self.target_user.mention} has been awarded the **{rep_role.name}** role!")
            except discord.Forbidden:
                await interaction.channel.send("⚠️ Error: Put my bot role HIGHER than the Rep role in server settings!")

        farewell_msg = "Thank you so much! Paalam po, closing this channel now..."
        asyncio.create_task(close_ticket_channel(interaction.channel, farewell_msg))


class TicketMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_selection(self, interaction: discord.Interaction, choice: str, label: str):
        user_target = None
        if interaction.channel.topic:
            match = re.search(r"\d+", interaction.channel.topic)
            if match:
                user_target = interaction.guild.get_member(int(match.group(0)))
        
        if not user_target:
            user_target = interaction.user 

        if interaction.user != user_target:
            await interaction.response.send_message("This menu is only for the ticket creator!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        await interaction.followup.send(f"You selected {label}!", ephemeral=True)

        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        staff_ping_text = f"{staff_role.mention if staff_role else '@Staff'}, a user needs assistance with **{choice.upper()}**"
        
        claim_view = StaffClaimView(choice=choice, target_user_id=user_target.id)
        await interaction.channel.send(content=staff_ping_text, view=claim_view)

    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.blurple, custom_id="ticket_menu:ps")
    async def partnership_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, "ps", "Partnership")

    @discord.ui.button(label="Claim Perks", style=discord.ButtonStyle.success, custom_id="ticket_menu:perks")
    async def perks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, "perks", "Claim Perks")

    @discord.ui.button(label="General Concerns", style=discord.ButtonStyle.secondary, custom_id="ticket_menu:concerns")
    async def concerns_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, "concerns", "Concerns")


class StaffClaimView(discord.ui.View):
    def __init__(self, choice: str = None, target_user_id: int = None):
        super().__init__(timeout=None)
        self.choice = choice
        self.target_user_id = target_user_id

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.danger, custom_id="staff_claim:claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if not staff_role or staff_role not in interaction.user.roles:
            await interaction.response.send_message("Only authorized staff can claim this!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        target_user = None
        if self.target_user_id:
            target_user = interaction.guild.get_member(self.target_user_id)
        else:
            async for msg in interaction.channel.history(limit=20, oldest_first=True):
                if msg.mentions:
                    target_user = msg.mentions[0]
                    break

        # 🔓 UNLOCK THE CHANNEL: Allow the user to type again
        if target_user:
            try:
                overwrite = interaction.channel.overwrites_for(target_user)
                overwrite.send_messages = True
                await interaction.channel.set_permissions(target_user, overwrite=overwrite, reason="Ticket claimed by staff")
            except discord.Forbidden:
                pass

        choice = self.choice or "general"
        if "assistance with PS" in interaction.message.content:
            choice = "ps"

        if choice == "ps":
            await interaction.channel.send(f"{interaction.user.mention} will be our rep")
            if target_user:
                asyncio.create_task(handle_partnership_workflow(interaction.client, interaction.channel, target_user))
        else:
            await interaction.channel.send(f"{interaction.user.mention} will be assisting you po")


# ==========================================
# EVENTS & LISTENERS
# ==========================================
@bot.event
async def on_ready():
    bot.add_view(TicketMenu())
    bot.add_view(StaffClaimView())
    
    if not update_presence.is_running():
        update_presence.start()
    
    print("------------------------------------------")
    print(f"Logged in as: {bot.user.name}")
    print("Bot is ACTIVE, views are persistent, and presence is looping!")
    print("------------------------------------------")

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if message.author.bot and "ticket" in message.channel.name.lower():
        full_text = message.content.lower()
        for embed in message.embeds:
            if embed.title: full_text += f" {embed.title.lower()}"
            if embed.description: full_text += f" {embed.description.lower()}"

        if "wassup" in full_text:
            user_target = None
            if message.mentions:
                user_target = message.mentions[0]
            else:
                match = re.search(r"<@!?(\d+)>", message.content)
                if match:
                    user_target = message.guild.get_member(int(match.group(1)))

            if not user_target:
                return

            try:
                await message.channel.edit(topic=f"Ticket Owner: {user_target.id}")
                
                # 🔒 LOCK THE CHANNEL: Prevent the user from typing
                overwrite = message.channel.overwrites_for(user_target)
                overwrite.send_messages = False
                await message.channel.set_permissions(user_target, overwrite=overwrite, reason="Locking ticket until claimed")
            except discord.Forbidden:
                pass

            welcome_text = (
                f"Hello {user_target.mention}, I'll be assisting your ticket today!\n\n"
                "**Please select an option below to proceed:**\n"
                "`Partnership` -- Form an alliance with our server\n"
                "`Claim Perks` -- Claim your server booster or milestone rewards\n"
                "`Concerns` -- Ask questions or report an issue\n\n"
                "-# Please click one of the buttons below to route your ticket."
            )
            
            await message.channel.send(content=welcome_text, view=TicketMenu())

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("CRITICAL ERROR: BOT_TOKEN is missing!")
    else:
        bot.run(BOT_TOKEN)


