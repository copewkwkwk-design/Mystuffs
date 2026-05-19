import asyncio
import discord
from discord.ext import commands
import re
import os

# ==========================================
# CONFIGURATION & CREDENTIALS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

STAFF_ROLE_ID = 1409944574541037678          
REP_ROLE_ID = 1421777773286129734            
PARTNERSHIP_CHANNEL_ID = 1409925659979022448   

# ==========================================
# INTERACTIVE UI VIEWS
# ==========================================
class TicketMenu(discord.ui.View):
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=None)
        self.target_user = target_user
        self.choice = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.target_user:
            await interaction.response.send_message("This menu is only for the ticket creator!", ephemeral=True)
            return False
        return True

    def disable_buttons(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.blurple)
    async def partnership_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "ps"
        await interaction.response.send_message("You selected Partnership!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Claim Perks", style=discord.ButtonStyle.success)
    async def perks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "perks"
        await interaction.response.send_message("You selected Claim Perks!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="General Concerns", style=discord.ButtonStyle.secondary)
    async def concerns_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "concerns"
        await interaction.response.send_message("You selected Concerns!", ephemeral=True)
        self.stop()


class StaffClaimView(discord.ui.View):
    def __init__(self, choice: str):
        super().__init__(timeout=None)
        self.choice = choice
        self.claimed_by = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if not staff_role or staff_role not in interaction.user.roles:
            await interaction.response.send_message("Only authorized staff can claim this!", ephemeral=True)
            return False
        return True

    def disable_buttons(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.danger)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.claimed_by = interaction.user
        
        if self.choice == "ps":
            await interaction.response.send_message(f"{interaction.user.mention} will be our rep")
        else:
            await interaction.response.send_message(f"{interaction.user.mention} will be assisting you po")
        self.stop()


# ==========================================
# BOT INITIALIZATION
# ==========================================
intents = discord.Intents.default()
intents.message_content = True  
intents.guilds = True  
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("------------------------------------------")
    print(f"Logged in as: {bot.user.name}")
    print("Bot is ACTIVE and ready to catch any ticket messages!")
    print("------------------------------------------")

# ==========================================
# WORKFLOW UTILITIES
# ==========================================
async def close_ticket_channel(channel: discord.TextChannel, final_message: str):
    await channel.send(final_message)
    await asyncio.sleep(5)
    await channel.delete()

async def handle_partnership_workflow(channel: discord.TextChannel, user_target: discord.Member):
    # Formatted safely to prevent line break errors
    welcome_msg = (
        f"{user_target.mention}, please drop your server's ad text below:\n"
        "*(Note: Your ad MUST contain a valid Discord Server link!)*"
    )
    await channel.send(welcome_msg)

    def check_ad(m):
        return m.author == user_target and m.channel == channel

    ad_message = None
    invite_regex = r"(?:https?://)?(?:www\.)?(?:discord\.gg/|discord(?:app)?\.com/invite/)[a-zA-Z0-9-]+"

    while True:
        try:
            msg = await bot.wait_for('message', check=check_ad, timeout=300)
            
            if re.search(invite_regex, msg.content):
                ad_message = msg
                break
            else:
                # FIXED: Formatted safely into blocks to prevent the f-string crash you got on Railway
                error_msg = (
                    f"⚠️ **Invalid ad!** {user_target.mention}, your message must contain a valid Discord invite link. "
                    "External links or text-only messages are not allowed.\n\n"
                    "Please post your ad again:"
                )
                await channel.send(error_msg)
                
        except asyncio.TimeoutError:
            await channel.send("Ticket timed out waiting for a valid advertisement text.")
            return

    ps_channel = bot.get_channel(PARTNERSHIP_CHANNEL_ID)
    if ps_channel:
        await ps_channel.send(content=f"**New Alliance!**\n\n{ad_message.content}\n\nPartnershiped with {user_target.mention}")
    
    await channel.send(f"{user_target.mention}, have you posted our server's advertisement on your end as well?\n*(Please type opo or wala pa po)*")

    def check_confirmation(m):
        return m.author == user_target and m.channel == channel and m.content.lower() in ["opo", "wala pa po"]

    try:
        confirm_msg = await bot.wait_for('message', check=check_confirmation, timeout=600)
        
        if confirm_msg.content.lower() == "opo":
            rep_role = channel.guild.get_role(REP_ROLE_ID)
            if rep_role:
                try:
                    await user_target.add_roles(rep_role)
                    await channel.send(f"🎉 {user_target.mention} has been awarded the {rep_role.name} role!")
                except discord.Forbidden:
                    await channel.send("⚠️ Error: Put my bot role HIGHER than the Rep role in server settings!")

            await close_ticket_channel(channel, "Thank you so much! Closing this channel now...")
            return
            
        if confirm_msg.content.lower() == "wala pa po":
            await channel.send("ok, tyt.\n-# type \"done\" if ok na")

            def check_done(m):
                return m.author == user_target and m.channel == channel and m.content.lower() == "done"

            try:
                await bot.wait_for('message', check=check_done, timeout=1200)
                rep_role = channel.guild.get_role(REP_ROLE_ID)
                if rep_role:
                    try:
                        await user_target.add_roles(rep_role)
                    except:
                        pass
                await close_ticket_channel(channel, "Thank you so much! Closing this channel now...")
            except asyncio.TimeoutError:
                await channel.send("Closed due to inactivity.")

    except asyncio.TimeoutError:
        pass


# ==========================================
# FOOLPROOF MESSAGE SCANNER
# ==========================================
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

            # Formatted safely to prevent line break errors
            welcome_text = (
                f"Hello {user_target.mention}, I'll be assisting your ticket today!\n\n"
                "**Please select an option below to proceed:**\n"
                "`Partnership` -- Form an alliance with our server\n"
                "`Claim Perks` -- Claim your server booster or milestone rewards\n"
                "`Concerns` -- Ask questions or report an issue\n\n"
                "-# Please click one of the buttons below to route your ticket."
            )
            
            menu_view = TicketMenu(target_user=user_target)
            initial_msg = await message.channel.send(content=welcome_text, view=menu_view)
            await menu_view.wait()
            
            menu_view.disable_buttons()
            await initial_msg.edit(view=menu_view)
            
            staff_role = message.guild.get_role(STAFF_ROLE_ID)
            staff_ping_text = f"{staff_role.mention if staff_role else '@Staff'}, a user needs assistance with {menu_view.choice.upper()}"
            
            claim_view = StaffClaimView(choice=menu_view.choice)
            claim_msg = await message.channel.send(content=staff_ping_text, view=claim_view)
            await claim_view.wait()
            
            claim_view.disable_buttons()
            await claim_msg.edit(view=claim_view)

            if menu_view.choice == "ps":
                await handle_partnership_workflow(message.channel, user_target)

# Safety check so the bot doesn't crash if you forget to add the token in Railway
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("CRITICAL ERROR: BOT_TOKEN is missing! Please set it in your Railway Environment Variables.")
    else:
        bot.run(BOT_TOKEN)

