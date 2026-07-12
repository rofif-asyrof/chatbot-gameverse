# -*- coding: utf-8 -*-

import os
import nest_asyncio
import requests
import random
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler
)

nest_asyncio.apply()
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Konfigurasi ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAWG_KEY = os.getenv("RAWG_KEY")

BASE_API_URL = "https://api.rawg.io/api"

# --- State untuk ConversationHandler ---
CHOOSING, AWAITING_SEARCH, AWAITING_PLATFORM, AWAITING_GENRE, AWAITING_DEVELOPER, AWAITING_STORE, AWAITING_TAG = range(7)

# --- PETA ID & NAMA ---
STORE_MAP = {
    "steam": (1, "Steam"), "playstation store": (3, "PlayStation Store"), "ps store": (3, "PlayStation Store"), "playstation": (3, "PlayStation Store"), "ps": (3, "PlayStation Store"),
    "xbox store": (2, "Xbox Store"), "xbox": (2, "Xbox Store"), "xbox 360 store": (7, "Xbox 360 Store"), "xbox 360": (7, "Xbox 360 Store"),
    "app store": (4, "App Store"), "apple app store": (4, "App Store"), "ios": (4, "App Store"),
    "google play": (8, "Google Play"), "android": (8, "Google Play"),
    "epic games": (11, "Epic Games"), "epic games store": (11, "Epic Games"), "epic": (11, "Epic Games"),
    "gog": (5, "GOG"), "nintendo store": (6, "Nintendo Store"), "nintendo": (6, "Nintendo Store"), "eshop": (6, "Nintendo Store"),
    "itch.io": (9, "itch.io"), "itch": (9, "itch.io"),
}

GENRE_MAP = {
    "action": ("action", "Action"), "indie": ("indie", "Indie"), "adventure": ("adventure", "Adventure"),
    "rpg": ("role-playing-games-rpg", "RPG"), "role playing games": ("role-playing-games-rpg", "RPG"),
    "strategy": ("strategy", "Strategy"), "shooter": ("shooter", "Shooter"), "casual": ("casual", "Casual"),
    "simulation": ("simulation", "Simulation"), "puzzle": ("puzzle", "Puzzle"), "arcade": ("arcade", "Arcade"),
    "platformer": ("platformer", "Platformer"), "racing": ("racing", "Racing"), "sports": ("sports", "Sports"),
    "fighting": ("fighting", "Fighting"), "family": ("family", "Family"),
    "board games": ("board-games", "Board Games"), "educational": ("educational", "Educational"), "card": ("card", "Card"),
}

PLATFORM_MAP = { "pc": 4, "macos": 5, "ps4": 18, "ps5": 187, "xbox series s/x": 186, "android": 21, "ios": 3 }

# --- Teks Bantuan yang Diperbarui ---
BANTUAN_TEKS = """
📖 *Panduan Penggunaan GameVerse* 📖

Halo! Bingung cara menggunakan GameVerse? Tenang, panduan ini akan menjelaskan semua fitur yang ada selangkah demi selangkah.

*Konsep Dasar:*

1. Pilih salah satu tombol kategori dari menu.

2. Bot akan memintamu untuk mengetik detail pencarian.

3. Kirim /cancel kapan saja untuk membatalkan aksimu.

------------------------------------------------------------------------------------------------
*Penjelasan Fitur Menu:*

*🔍 Cari Game*
    • *Fungsi:* Untuk mencari game spesifik berdasarkan judulnya.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik nama game yang ingin dicari (contoh: `Elden Ring`).

*🎮 Platform*
    • *Fungsi:* Menampilkan game-game populer untuk konsol atau platform tertentu.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik nama platform (contoh: `pc`, `ps5`).

*🧩 Genre*
    • *Fungsi:* Mencari game berdasarkan genre yang kamu suka.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik nama genre (contoh: `rpg`, `strategy`).

*🏷️ Tag*
    • *Fungsi:* Untuk pencarian super spesifik menggunakan tag deskriptif.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik tag yang kamu inginkan (contoh: `open-world`, `multiplayer`).

*👨‍💻 Developer*
    • *Fungsi:* Menampilkan game yang dibuat oleh developer tertentu.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik nama developer (contoh: `FromSoftware`).

*🏪 Toko Game*
    • *Fungsi:* Melihat game yang tersedia di toko digital tertentu.
    • *Cara Pakai:* Tekan tombol ini, lalu ketik nama toko (contoh: `steam`, `epic games`).

------------------------------------------------------------------------------------------------

⭐ *Tips Profesional: Filter Tahun!*
Kamu bisa menambahkan tahun rilis pada pencarian Platform, Genre, Tag, dll.
    • * contoh 1:* Cari game PC rilisan 2024? Tekan `🎮 Platform`, lalu ketik `pc 2024`.
    • *Contoh 2:* Cari game RPG dari 2020-2023? Tekan `🧩 Genre`, lalu ketik `rpg 2020-2023`.

------------------------------------------------------------------------------------------------

*Perintah Penting:*
• /start - Untuk menampilkan menu utama kapan saja.
• /cancel - Untuk membatalkan aksi saat ini dan kembali ke menu utama.

Semoga panduan ini membantu!
"""

def parse_date_filter(date_input: str):
    try:
        if '-' in date_input:
            start_year, end_year = map(int, date_input.split('-'))
            current_year = datetime.now().year
            if 1900 <= start_year <= current_year and 1900 <= end_year <= current_year and start_year <= end_year:
                return (start_year, end_year)
        elif date_input.isdigit():
            year = int(date_input)
            current_year = datetime.now().year
            if 1900 <= year <= current_year:
                return (year, year)
    except (ValueError, IndexError):
        return None
    return None

async def fetch_and_send_game_details(update: Update, context: ContextTypes.DEFAULT_TYPE, game_summary: dict):
    if not game_summary or "slug" not in game_summary:
        await update.message.reply_text("Gagal mendapatkan detail game (data tidak lengkap).")
        return

    try:
        game_slug = game_summary["slug"]
        detail_url = f"{BASE_API_URL}/games/{game_slug}?key={RAWG_KEY}"
        res = requests.get(detail_url)
        res.raise_for_status()
        game = res.json()
        
        name = game.get("name", "N/A")
        image = game.get("background_image", game_summary.get("background_image"))
        released = game.get("released", "N/A")
        rating = game.get("rating", "N/A")
        metacritic = game.get("metacritic")
        rawg_link = f"https://rawg.io/games/{game['slug']}"
        platforms = ", ".join(p["platform"]["name"] for p in game.get("platforms", []))
        genres = ", ".join(g["name"] for g in game.get("genres", []))
        developers = ", ".join(d["name"] for d in game.get("developers", []))
        stores = ", ".join(s["store"]["name"] for s in game.get("stores", []))
        english_tags = [t["name"] for t in game.get("tags", []) if t.get("language") == "eng"]
        tags = ", ".join(english_tags[:7])
        metacritic_text = f"Ⓜ️ Metascore: {metacritic}\n" if metacritic else ""
        
        caption = (f"*🎮 {name}*\n📅 Rilis: {released}\n⭐ Rating: {rating}\n{metacritic_text}"
                   f"🖥️ Platform: {platforms or 'N/A'}\n🧩 Genre: {genres or 'N/A'}\n"
                   f"👨‍💻 Developer: {developers or 'N/A'}\n🏪 Toko: {stores or 'N/A'}\n"
                   f"🏷️ Tag: {tags or 'N/A'}\n\n[🔗 Detail Lengkap di RAWG]({rawg_link})")
                   
        if image: 
            await update.message.reply_photo(photo=image, caption=caption, parse_mode="Markdown")
        else: 
            await update.message.reply_text(caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error saat memproses game {game_summary.get('slug')}: {e}")
        await update.message.reply_text(f"Gagal menampilkan detail untuk game: {game_summary.get('name')}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [KeyboardButton("🔍 Cari Game"), KeyboardButton("🎮 Platform")], 
        [KeyboardButton("🧩 Genre"), KeyboardButton("🏷️ Tag")], 
        [KeyboardButton("👨‍💻 Developer"), KeyboardButton("🏪 Toko Game")], 
        [KeyboardButton("❓ Bantuan")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_text = f"Halo, {update.effective_user.first_name}! 👋\n\nSelamat datang di Bot Pencari Game. Silakan pilih menu di bawah."
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return CHOOSING

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(BANTUAN_TEKS, parse_mode="Markdown")
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Aksi dibatalkan.")
    return await start(update, context)

async def ask_for_input(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state: int, prompt_text: str):
    await update.message.reply_text(prompt_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return next_state

async def ask_for_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await ask_for_input(update, context, AWAITING_SEARCH, "Silakan ketik nama game yang ingin Anda cari:\n\n_(Ketik /cancel untuk membatalkan)_")

async def ask_for_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = f"Silakan ketik nama platform (opsional: tambahkan tahun).\nContoh: `pc` atau `pc 2022`\n\n*Pilihan:*\n`{', '.join(PLATFORM_MAP.keys())}`\n\n_(Ketik /cancel untuk membatalkan)_"
    return await ask_for_input(update, context, AWAITING_PLATFORM, prompt)

async def ask_for_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = f"Silakan ketik nama genre (opsional: tambahkan tahun).\n contoh: `action` atau `action 2021`\n\n*Pilihan:*\n`{', '.join(sorted(list(set(v[1] for v in GENRE_MAP.values()))))}`\n\n_(Ketik /cancel untuk membatalkan)_"
    return await ask_for_input(update, context, AWAITING_GENRE, prompt)

async def ask_for_developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = f"Silakan ketik nama developer (opsional: tambahkan tahun).\nContoh: `ubisoft` atau `ubisoft 2023`\n\n*Contoh Terkenal:*\n`Rockstar Games, Nintendo, FromSoftware, Ubisoft, Valve`\n\n_(Ketik /cancel untuk membatalkan)_"
    return await ask_for_input(update, context, AWAITING_DEVELOPER, prompt)

async def ask_for_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = f"Silakan ketik nama toko (opsional: tambahkan tahun).\nContoh: `steam` atau `steam 2023`\n\n*Pilihan:*\n`{', '.join(sorted(list(set(v[1] for v in STORE_MAP.values()))))}`\n\n_(Ketik /cancel untuk membatalkan)_"
    return await ask_for_input(update, context, AWAITING_STORE, prompt)

async def ask_for_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = f"Silakan ketik nama tag (opsional: tambahkan tahun).\nContoh: `singleplayer` atau `singleplayer 2020`\n\n*Contoh Populer:*\n`singleplayer, multiplayer, open-world, story-rich, co-op`\n\n_(Ketik /cancel untuk membatalkan)_"
    return await ask_for_input(update, context, AWAITING_TAG, prompt)

async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    search_query = update.message.text
    await update.message.reply_text(f"Mencari game yang cocok dengan '{search_query}'...")
    url = f"{BASE_API_URL}/games?key={RAWG_KEY}&search={search_query}&page_size=1"
    
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("results"): 
            await update.message.reply_text(f"Game '{search_query}' tidak ditemukan.")
        else: 
            await fetch_and_send_game_details(update, context, data["results"][0])
    except Exception as e:
        logger.error(f"Error in process_search: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

async def process_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    args = update.message.text.split()
    date_filter_input = None
    if args and ('-' in args[-1] or args[-1].isdigit()): 
        date_filter_input = args[-1]
        name_parts = args[:-1]
    else: 
        name_parts = args
        
    platform_name = " ".join(name_parts).lower()
    platform_id = PLATFORM_MAP.get(platform_name)
    if not platform_id: 
        await update.message.reply_text(f"Platform '{platform_name}' tidak ditemukan.")
        return await start(update, context)

    games_to_show = []
    title = ""
    base_url = f"{BASE_API_URL}/games?key={RAWG_KEY}&platforms={platform_id}&ordering=-popularity"

    try:
        if date_filter_input:
            date_range = parse_date_filter(date_filter_input)
            if not date_range: 
                await update.message.reply_text("Format tahun tidak valid.")
                return await start(update, context)
            start_year, end_year = date_range
            api_date_range = f"{start_year}-01-01,{end_year}-12-31"
            url = f"{base_url}&dates={api_date_range}&page_size=3"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_to_show = data.get("results", [])
            title = f"🎮 3 Game Terpopuler ({date_filter_input}) untuk Platform: *{platform_name.upper()}*"
        else:
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            date_range_str = f"{three_years_ago.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')}"
            url = f"{base_url}&dates={date_range_str}&page_size=30"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_list = data.get("results")
            if games_list: 
                games_to_show = random.sample(games_list, k=min(3, len(games_list)))
            title = f"🎮 3 Game Populer Acak (3 Tahun Terakhir) untuk Platform: *{platform_name.upper()}*"

        if not games_to_show: 
            await update.message.reply_text("Tidak ada data game populer untuk kriteria ini.")
        else:
            await update.message.reply_text(title, parse_mode="Markdown")
            for game in games_to_show: 
                await fetch_and_send_game_details(update, context, game)
    except Exception as e:
        logger.error(f"Error in process_platform: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

async def process_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    args = update.message.text.split()
    date_filter_input = None
    if args and ('-' in args[-1] or args[-1].isdigit()): 
        date_filter_input = args[-1]
        name_parts = args[:-1]
    else: 
        name_parts = args
        
    user_genre_name = " ".join(name_parts).lower()
    genre_data = GENRE_MAP.get(user_genre_name)
    if not genre_data: 
        await update.message.reply_text(f"Genre '{user_genre_name}' tidak ditemukan.")
        return await start(update, context)
    genre_slug, genre_actual_name = genre_data

    games_to_show = []
    title = ""
    base_url = f"{BASE_API_URL}/games?key={RAWG_KEY}&genres={genre_slug}&ordering=-popularity"

    try:
        if date_filter_input:
            date_range = parse_date_filter(date_filter_input)
            if not date_range: 
                await update.message.reply_text("Format tahun tidak valid.")
                return await start(update, context)
            start_year, end_year = date_range
            api_date_range = f"{start_year}-01-01,{end_year}-12-31"
            url = f"{base_url}&dates={api_date_range}&page_size=3"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_to_show = data.get("results", [])
            title = f"🎮 3 Game Terpopuler ({date_filter_input}) dari Genre: *{genre_actual_name}*"
        else:
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            date_range_str = f"{three_years_ago.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')}"
            url = f"{base_url}&dates={date_range_str}&page_size=30"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_list = data.get("results")
            if games_list: 
                games_to_show = random.sample(games_list, k=min(3, len(games_list)))
            title = f"🎮 3 Game Populer Acak dari Genre: *{genre_actual_name}*"

        if not games_to_show: 
            await update.message.reply_text(f"Tidak ada data game untuk genre '{genre_actual_name}' pada kriteria yang diminta.")
        else:
            await update.message.reply_text(title, parse_mode="Markdown")
            for game in games_to_show: 
                await fetch_and_send_game_details(update, context, game)
    except Exception as e:
        logger.error(f"Error in process_genre: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

async def process_developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    args = update.message.text.split()
    date_filter_input = None
    if args and ('-' in args[-1] or args[-1].isdigit()): 
        date_filter_input = args[-1]
        name_parts = args[:-1]
    else: 
        name_parts = args
        
    developer_name = " ".join(name_parts)
    dev_search_url = f"{BASE_API_URL}/developers?key={RAWG_KEY}&search={developer_name}&page_size=1"
    
    try:
        dev_res = requests.get(dev_search_url)
        dev_res.raise_for_status()
        dev_data = dev_res.json()
        
        if not dev_data.get("results"): 
            await update.message.reply_text(f"Developer '{developer_name}' tidak ditemukan.")
            return await start(update, context)
            
        developer_slug = dev_data["results"][0]["slug"]
        developer_actual_name = dev_data["results"][0]["name"]

        games_to_show = []
        title = ""
        base_url = f"{BASE_API_URL}/games?key={RAWG_KEY}&developers={developer_slug}&ordering=-popularity"

        if date_filter_input:
            date_range = parse_date_filter(date_filter_input)
            if not date_range: 
                await update.message.reply_text("Format tahun tidak valid.")
                return await start(update, context)
            start_year, end_year = date_range
            api_date_range = f"{start_year}-01-01,{end_year}-12-31"
            url = f"{base_url}&dates={api_date_range}&page_size=3"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_to_show = data.get("results", [])
            title = f"🎮 3 Game Terpopuler ({date_filter_input}) dari *{developer_actual_name}*:"
        else:
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            date_range_str = f"{three_years_ago.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')}"
            url = f"{base_url}&dates={date_range_str}&page_size=30"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_list = data.get("results")
            if games_list: 
                games_to_show = random.sample(games_list, k=min(3, len(games_list)))
            title = f"🎮 3 Game Populer Acak dari *{developer_actual_name}*:"

        if not games_to_show: 
            await update.message.reply_text(f"Tidak ada data game ditemukan untuk developer '{developer_actual_name}' pada kriteria yang diminta.")
        else:
            await update.message.reply_text(title, parse_mode="Markdown")
            for game in games_to_show: 
                await fetch_and_send_game_details(update, context, game)
    except Exception as e:
        logger.error(f"Error in process_developer: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

async def process_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    args = update.message.text.split()
    date_filter_input = None
    if args and ('-' in args[-1] or args[-1].isdigit()): 
        date_filter_input = args[-1]
        name_parts = args[:-1]
    else: 
        name_parts = args
        
    user_store_name = " ".join(name_parts).lower()
    store_data = STORE_MAP.get(user_store_name)
    if not store_data: 
        await update.message.reply_text(f"Toko '{user_store_name}' tidak ditemukan.")
        return await start(update, context)
    store_id, store_actual_name = store_data

    games_to_show = []
    title = ""
    base_url = f"{BASE_API_URL}/games?key={RAWG_KEY}&stores={store_id}&ordering=-popularity"

    try:
        if date_filter_input:
            date_range = parse_date_filter(date_filter_input)
            if not date_range: 
                await update.message.reply_text("Format tahun tidak valid.")
                return await start(update, context)
            start_year, end_year = date_range
            api_date_range = f"{start_year}-01-01,{end_year}-12-31"
            url = f"{base_url}&dates={api_date_range}&page_size=3"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_to_show = data.get("results", [])
            title = f"🎮 3 Game Terpopuler ({date_filter_input}) dari *{store_actual_name}*:"
        else:
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            date_range_str = f"{three_years_ago.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')}"
            url = f"{base_url}&dates={date_range_str}&page_size=30"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_list = data.get("results")
            if games_list: 
                games_to_show = random.sample(games_list, k=min(3, len(games_list)))
            title = f"🎮 3 Game Populer Acak dari *{store_actual_name}*:"

        if not games_to_show: 
            await update.message.reply_text(f"Tidak ada data game ditemukan untuk toko '{store_actual_name}' pada kriteria yang diminta.")
        else:
            await update.message.reply_text(title, parse_mode="Markdown")
            for game in games_to_show: 
                await fetch_and_send_game_details(update, context, game)
    except Exception as e:
        logger.error(f"Error in process_store: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

async def process_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: 
        await update.message.reply_text("Invalid input received.")
        return await start(update, context)
        
    args = update.message.text.split()
    date_filter_input = None
    if args and ('-' in args[-1] or args[-1].isdigit()): 
        date_filter_input = args[-1]
        name_parts = args[:-1]
    else: 
        name_parts = args
        
    search_query = " ".join(name_parts)
    tag_search_url = f"{BASE_API_URL}/tags?key={RAWG_KEY}&search={search_query}&page_size=1"
    
    try:
        tag_res = requests.get(tag_search_url)
        tag_res.raise_for_status()
        tag_data = tag_res.json()
        
        if not tag_data.get("results"): 
            await update.message.reply_text(f"Tag '{search_query}' tidak ditemukan.")
            return await start(update, context)
            
        correct_tag_slug = tag_data["results"][0]["slug"]
        correct_tag_name = tag_data["results"][0]["name"]

        games_to_show = []
        title = ""
        base_url = f"{BASE_API_URL}/games?key={RAWG_KEY}&tags={correct_tag_slug}&ordering=-popularity"

        if date_filter_input:
            date_range = parse_date_filter(date_filter_input)
            if not date_range: 
                await update.message.reply_text("Format tahun tidak valid.")
                return await start(update, context)
            start_year, end_year = date_range
            api_date_range = f"{start_year}-01-01,{end_year}-12-31"
            url = f"{base_url}&dates={api_date_range}&page_size=3"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_to_show = data.get("results", [])
            title = f"🎮 3 Game Terpopuler ({date_filter_input}) dengan Tag: *{correct_tag_name}*"
        else:
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            date_range_str = f"{three_years_ago.strftime('%Y-%m-%d')},{today.strftime('%Y-%m-%d')}"
            url = f"{base_url}&dates={date_range_str}&page_size=30"
            
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            games_list = data.get("results")
            if games_list: 
                games_to_show = random.sample(games_list, k=min(3, len(games_list)))
            title = f"🎮 3 Game Populer Acak dengan Tag: *{correct_tag_name}*"

        if not games_to_show: 
            await update.message.reply_text(f"Tidak ada data game ditemukan untuk tag '{correct_tag_name}' pada kriteria yang diminta.")
        else:
            await update.message.reply_text(title, parse_mode="Markdown")
            for game in games_to_show: 
                await fetch_and_send_game_details(update, context, game)
    except Exception as e:
        logger.error(f"Error in process_tag: {e}")
        await update.message.reply_text("Maaf, layanan sedang bermasalah, silakan coba lagi nanti.")
        
    return await start(update, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("^🔍 Cari Game$"), ask_for_search),
                MessageHandler(filters.Regex("^🎮 Platform$"), ask_for_platform),
                MessageHandler(filters.Regex("^🧩 Genre$"), ask_for_genre),
                MessageHandler(filters.Regex("^👨‍💻 Developer$"), ask_for_developer),
                MessageHandler(filters.Regex("^🏪 Toko Game$"), ask_for_store),
                MessageHandler(filters.Regex("^🏷️ Tag$"), ask_for_tag),
                MessageHandler(filters.Regex("^❓ Bantuan$"), bantuan),
            ],
            AWAITING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_search)],
            AWAITING_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_platform)],
            AWAITING_GENRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_genre)],
            AWAITING_DEVELOPER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_developer)],
            AWAITING_STORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_store)],
            AWAITING_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_tag)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot Telegram siap dijalankan...")
    app.run_polling() 

if __name__ == '__main__':
    main()
