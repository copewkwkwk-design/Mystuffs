import asyncio
import discord
from discord.ext import commands
import re
import os

# ==========================================
# CONFIGURATION & CREDENTIALS
# ==========================================
# Securely fetch the token from Railway's environment variables
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
    await channel.send(f"{user_target.mention}, please drop your server's ad text below:\n*(Note: Your ad MUST contain a valid Discord Server link!)*")

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
                await channel.send(f"⚠️ **Invalid ad!** {user_target.mention}, your message must contain a valid Discord invite link. External links or text-only
