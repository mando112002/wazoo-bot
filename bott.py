import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import json
import os
import csv
import urllib.parse

# ================== CONFIG ==================

TOKEN = os.getenv("DISCORD_TOKEN")

BASE_IMAGE_PATH = "base.jpg"
OUTPUT_DIR = "generated"
DATA_FILE = "data.json"
SUBMISSIONS_FILE = "submissions.json"

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

os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"last_id": 0}, f)

if not os.path.exists(SUBMISSIONS_FILE):
    with open(SUBMISSIONS_FILE, "w") as f:
        json.dump([], f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_submissions():
    with open(SUBMISSIONS_FILE, "r") as f:
        return json.load(f)

def save_submissions(items):
    with open(SUBMISSIONS_FILE, "w") as f:
        json.dump(items, f, indent=4)

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
    uid = str(interaction.user.id)

    # منع الإعادة فقط لو المستخدم كمل Submit قبل كده
    submissions = load_submissions()
    for s in submissions:
        if s["user_id"] == uid:
            await interaction.followup.send(
                "You already completed this process and cannot submit again.",
                ephemeral=True
            )
            return None

    data = load_data()
    data["last_id"] += 1
    new_id = data["last_id"]
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

    # ===== LOAD FONTS =====
    try:
        font_role = ImageFont.truetype("Cinzel-VariableFont_wght.ttf", 28)
        font_name = ImageFont.truetype("Allura-Regular.ttf", 44)
    except Exception as e:
        print("Font load failed, using default font:", e)
        font_role = ImageFont.load_default()
        font_name = ImageFont.load_default()

    role_text = f"{role_name} | ID: #{new_id}"

    # Role + ID layer
    role_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    role_draw = ImageDraw.Draw(role_layer)
    role_position = (470, 560)
    role_draw.text(role_position, role_text, fill=(0, 0, 0, 255), font=font_role)
    role_layer = role_layer.rotate(ROLE_TEXT_ANGLE, resample=Image.BICUBIC, expand=False)
    base = Image.alpha_composite(base, role_layer)

    # Username layer
    name_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    name_draw = ImageDraw.Draw(name_layer)
    name_position = (350, 635)
    name_draw.text(name_position, username, fill=(0, 0, 0, 255), font=font_name)
    name_layer = name_layer.rotate(NAME_TEXT_ANGLE, resample=Image.BICUBIC, expand=False)
    base = Image.alpha_composite(base, name_layer)

    output_path = os.path.join(OUTPUT_DIR, f"pass_{new_id}.png")
    base.save(output_path)

    return {
        "pass_id": new_id,
        "role": role_name,
        "username": username,
        "image_path": output_path
    }

def build_twitter_text(pass_id: int, role: str):
    return (
        f"Just generated my Wazoo Pass ID: #{pass_id} 🎟️\n"
        f"Role: {role}\n\n"
        f"Join the gang 👀🔥\n"
        f"DC : https://discord.com/invite/wazoogang\n"
        f"X : @WazooGangg"
    )

def twitter_intent_url(text: str):
    return "https://x.com/intent/tweet?text=" + urllib.parse.quote(text)

# ================== USER STATE ==================

temp_state = {}

# ================== VIEWS & MODALS ==================

class GenerateFlowView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Generate", style=discord.ButtonStyle.primary, custom_id="btn_generate")
    async def generate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        result = await generate_pass(interaction)
        if result is None:
            return

        temp_state[str(interaction.user.id)] = {
            "pass_id": result["pass_id"],
            "role": result["role"],
            "image_path": result["image_path"]
        }

        caption = build_twitter_text(result["pass_id"], result["role"])
        twitter_url = twitter_intent_url(caption)

        await interaction.followup.send(
            content=caption,
            file=discord.File(result["image_path"]),
            view=PostView(twitter_url),
            ephemeral=True
        )

class PostView(discord.ui.View):
    def __init__(self, twitter_url: str):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Open on X",
                style=discord.ButtonStyle.link,
                url=twitter_url
            )
        )

    @discord.ui.button(label="Post Link", style=discord.ButtonStyle.secondary, custom_id="btn_post_link", row=1)
    async def post_link_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PostLinkModal())

class SubmitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.primary, custom_id="btn_submit")
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WalletModal())

class PostLinkModal(discord.ui.Modal, title="Submit Twitter Post Link"):
    link = discord.ui.TextInput(label="Twitter/X Post Link", placeholder="https://x.com/...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in temp_state:
            await interaction.response.send_message("Please generate first.", ephemeral=True)
            return

        temp_state[uid]["twitter_link"] = str(self.link)

        await interaction.response.send_message(
            "Link saved. Now click **Submit** and enter your wallet.",
            view=SubmitView(),
            ephemeral=True
        )

class WalletModal(discord.ui.Modal, title="Submit Wallet (EVM)"):
    wallet = discord.ui.TextInput(label="Wallet Address (0x...)", placeholder="0x...", required=True, min_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in temp_state:
            await interaction.response.send_message("Please generate first.", ephemeral=True)
            return

        wallet_addr = str(self.wallet).strip()
        if not wallet_addr.lower().startswith("0x"):
            await interaction.response.send_message("Invalid wallet. Must start with 0x", ephemeral=True)
            return

        state = temp_state[uid]
        twitter_link = state.get("twitter_link")
        if not twitter_link:
            await interaction.response.send_message("Please submit your Twitter post link first.", ephemeral=True)
            return

        submissions = load_submissions()
        submissions.append({
            "user_id": uid,
            "username": interaction.user.name,
            "role": state["role"],
            "pass_id": state["pass_id"],
            "twitter_link": twitter_link,
            "wallet": wallet_addr
        })
        save_submissions(submissions)

        del temp_state[uid]

        await interaction.response.send_message("Submitted successfully! ✅", ephemeral=True)

# ================== SLASH COMMANDS ==================

@bot.tree.command(name="post", description="Post the Generate button (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def post_cmd(interaction: discord.Interaction):
    view = GenerateFlowView()

    await interaction.response.send_message(
        content="**Generate your Pass and submit your wallet**",
        file=discord.File("generate_banner.jpg"),
        view=view
    )


@bot.tree.command(name="export", description="Export submissions as CSV (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def export_cmd(interaction: discord.Interaction):
    submissions = load_submissions()

    csv_path = "submissions.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "username", "role", "pass_id", "twitter_link", "wallet"])
        writer.writeheader()
        for row in submissions:
            writer.writerow(row)

    await interaction.response.send_message(
        "Here is the exported CSV:",
        file=discord.File(csv_path),
        ephemeral=True
    )

# ================== RUN ==================

bot.run(TOKEN)
