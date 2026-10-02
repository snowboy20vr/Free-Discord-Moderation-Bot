import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
PREFIX = os.getenv('PREFIX', '!').strip() or '!'
DATABASE_PATH = os.getenv('DATABASE_PATH', 'moderation.db').strip() or 'moderation.db'
OWNER_IDS = {int(value.strip()) for value in os.getenv('OWNER_IDS', '').split(',') if value.strip().isdigit()}

if not TOKEN:
    raise RuntimeError('DISCORD_TOKEN is missing. Put it in your .env file.')
