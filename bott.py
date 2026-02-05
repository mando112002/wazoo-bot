import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import json
import os

# ================== CONFIG ==================

TOKEN = os.getenv("DISCORD_TOKEN")

BASE_IMAGE_PATH = "base.jpg"
OUTPUT_DIR = "generated"
DATA_FILE = "data.json"

ROLE_PRIORITY = [
    ("Legendary Monster", "Treasury"),
    ("Real Fugz", "Treasury"),
    ("OG Gang", "OG"),
    ("Real Fugger", "OG"),
    ("FCFS Gang", "WL"),
    ("Fugz Holder", "WL"),
]

# Angles
TILT_ANGLE = 10          # avatar angle
ROLE_TEXT_ANGLE = 9      # role + ID angle
NAME_TEXT_ANGLE = 10     # username angle

# ================== BOT SETUP ==================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== STORAGE ==================

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"last_id": 0, "used_users": []}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user_role(member: discord.Member):
    role_names = [role.name for role in member.roles]
    for discord_role, display_role in ROLE_PRIORITY:
        if discord_role in role_names:
            return display_role
    return "Member"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync failed: {e}")

# ================== GENERATION LOGIC ==================

async def generate_pass(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id in data["used_users"]:
        await interaction.followup.send("You already generated your pass.", ephemeral=True)
        return

    data["last_id"] += 1
    new_id = data["last_id"]
    data["used_users"].append(user_id)
    save_data(data)

    role_name = get_user_role(interaction.user)
    username = interaction.user.name

    avatar_url = interaction.user.display_avatar.url
    try:
        response = requests.get(avatar_url, timeout=10)
        response.raise_for_status()
        avatar_img = Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        fallback_url = interaction.user.display_avatar.replace(size=128).url
        response = requests.get(fallback_url, timeout=10)
        response.raise_for_status()
        avatar_img = Image.open(BytesIO(response.content)).convert("RGBA")

    base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    base = base.copy()

    avatar_size = (200, 200)
    avatar_img = avatar_img.resize(avatar_size)
    avatar_img = avatar_img.rotate(TILT_ANGLE, resample=Image.BICUBIC, expand=True)

    avatar_position = (250, 428)
    base.paste(avatar_img, avatar_position, avatar_img)

    # ===== LOAD FONTS (from project folder) =====
    try:
        font_role = ImageFont.truetype("Cinzel-VariableFont_wght.ttf", 28)   # Role + ID
        font_name = ImageFont.truetype("Allura-Regular.ttf", 44)             # Signature name
    except Exception as e:
        print("Font load failed, using default font:", e)
        font_role = ImageFont.load_default()
        font_name = ImageFont.load_default()

    role_text = f"{role_name} | ID: #{new_id}"

    # ===== Role + ID layer =====
    role_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    role_draw = ImageDraw.Draw(role_layer)
    role_position = (480, 560)
    role_draw.text(role_position, role_text, fill=(0, 0, 0, 255), font=font_role)
    role_layer = role_layer.rotate(ROLE_TEXT_ANGLE, resample=Image.BICUBIC, expand=False)
    base = Image.alpha_composite(base, role_layer)

    # ===== Username (Signature) layer =====
    name_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    name_draw = ImageDraw.Draw(name_layer)
    name_position = (350, 635)
    name_draw.text(name_position, username, fill=(0, 0, 0, 255), font=font_name)
    name_layer = name_layer.rotate(NAME_TEXT_ANGLE, resample=Image.BICUBIC, expand=False)
    base = Image.alpha_composite(base, name_layer)

    output_path = os.path.join(OUTPUT_DIR, f"pass_{new_id}.png")
    base.save(output_path)

    caption = (
        f"Just generated my Wazoo Pass 🎟️\n"
        f"Role: {role_name}\n"
        f"ID: #{new_id}\n\n"
        f"Join the gang 👀🔥\n"
        f"https://discord.com/invite/wazoogang"
    )

    await interaction.followup.send(
        content=caption,
        file=discord.File(output_path),
        ephemeral=True
    )

# ================== BUTTON VIEW ==================

class GenerateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Generate Pass", style=discord.ButtonStyle.primary, custom_id="generate_pass_btn")
    async def generate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await generate_pass(interaction)

# ================== SLASH COMMAND: /post ==================

@bot.tree.command(name="post", description="Post the Generate Pass button")
@discord.app_commands.checks.has_permissions(administrator=True)
async def post(interaction: discord.Interaction):
    view = GenerateView()
    await interaction.response.send_message("Click the button to generate your pass:", view=view)

@post.error
async def post_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You need Administrator permission to use this command.", ephemeral=True)

# ================== RUN ==================

bot.run(TOKEN)
