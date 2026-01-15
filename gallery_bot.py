import asyncio
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Токен бота из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# ID администратора из .env
ADMIN_ID = os.getenv("ADMIN_ID")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не найден в .env файле!")

# Файлы данных из .env (с значениями по умолчанию)
DATA_FILE = os.getenv("DATA_FILE", "gallery_data.json")
FILES_DIR = os.getenv("FILES_DIR", "gallery_files")
LOGS_FILE = os.getenv("LOGS_FILE", "error_logs.json")

# Создаем папку для файлов если её нет
os.makedirs(FILES_DIR, exist_ok=True)


def load_data():
    """Загрузка данных из файла"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "galleries": {}, "invites": {}}


def save_data(data):
    """Сохранение данных в файл"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_logs():
    """Загрузка логов ошибок"""
    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"errors": []}


def save_log(error_text: str):
    """Сохранение ошибки в лог"""
    logs = load_logs()
    logs["errors"].append({
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "error": error_text
    })
    # Храним только последние 50 ошибок
    logs["errors"] = logs["errors"][-50:]
    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def get_user_id(update: Update) -> str:
    """Получить ID пользователя как строку"""
    return str(update.effective_user.id)


def get_username(update: Update) -> str:
    """Получить username или имя пользователя"""
    user = update.effective_user
    return user.username or user.first_name or f"user_{user.id}"


def is_banned(user_id: str) -> bool:
    """Проверить забанен ли пользователь"""
    data = load_data()
    return user_id in data.get("banned_users", [])


# ============ ГЛАВНОЕ МЕНЮ ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    data = load_data()
    user_id = get_user_id(update)
    
    # Проверяем бан
    if is_banned(user_id):
        await update.message.reply_text("🚫 Вы заблокированы в этом боте.")
        return
    
    # Регистрируем пользователя
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "username": get_username(update),
            "friends": []
        }
        save_data(data)
    
    # Проверяем входящие приглашения
    if user_id in data.get("invites", {}):
        await show_pending_invites(update, context)
        return
    
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    """Показать главное меню"""
    # Определяем user_id
    if update.callback_query:
        user_id = str(update.callback_query.from_user.id)
    else:
        user_id = str(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton("📖 О боте", callback_data="about")],
        [InlineKeyboardButton("🖼 Галерея", callback_data="gallery")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")]
    ]
    
    # Кнопка админ панели только для админа
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔐 Админ панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👋 Добро пожаловать в Галерею!\n\nВыберите действие:"
    
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


# ============ О БОТЕ ============

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о боте"""
    query = update.callback_query
    await query.answer()
    
    text = """*Бот Галерея*

Этот бот позволяет создавать совместные галереи с друзьями!

📌 *Возможности:*
• Создавайте совместные галереи
• Загружать фото и видео
• Делиться воспоминаниями

Созданно при поддержке очень красивой дамы❤️"""
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


# ============ ГАЛЕРЕЯ ============

async def show_gallery_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню галереи со списком друзей"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    
    keyboard = [[InlineKeyboardButton("➕ Добавить друга", callback_data="add_friend")]]
    
    # Список друзей с галереями
    user_data = data["users"].get(user_id, {})
    friends = user_data.get("friends", [])
    
    # Получаем кастомные имена
    nicknames = user_data.get("nicknames", {})
    
    for friend_id in friends:
        friend_data = data["users"].get(friend_id, {})
        # Используем кастомное имя если есть, иначе username
        friend_name = nicknames.get(friend_id) or friend_data.get("username", f"user_{friend_id}")
        keyboard.append([
            InlineKeyboardButton(f"👤 {friend_name}", callback_data=f"view_gallery_{friend_id}"),
            InlineKeyboardButton("✏️", callback_data=f"rename_friend_{friend_id}"),
            InlineKeyboardButton("💬", callback_data=f"start_chat_{friend_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if friends:
        text = "🖼 *Ваши галереи*\n\nВыберите друга для просмотра совместной галереи:"
    else:
        text = "🖼 *Ваши галереи*\n\nУ вас пока нет совместных галерей.\nДобавьте друга, чтобы начать!"
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


# ============ ПЕРЕИМЕНОВАНИЕ ДРУГА ============

async def rename_friend_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Запрос нового имени для друга"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    friend_data = data["users"].get(friend_id, {})
    friend_username = friend_data.get("username", f"user_{friend_id}")
    
    context.user_data["waiting_for"] = "friend_nickname"
    context.user_data["rename_friend_id"] = friend_id
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="gallery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✏️ *Переименование*\n\n"
        f"Текущее имя: @{friend_username}\n\n"
        f"Введите новое имя (до 20 символов):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_friend_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нового имени друга"""
    MAX_NICKNAME_LENGTH = 20
    nickname = update.message.text.strip()
    friend_id = context.user_data.get("rename_friend_id")
    
    context.user_data["waiting_for"] = None
    
    if len(nickname) > MAX_NICKNAME_LENGTH:
        await update.message.reply_text(
            f"❌ Имя слишком длинное!\nМаксимум {MAX_NICKNAME_LENGTH} символов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"rename_friend_{friend_id}")]])
        )
        return
    
    data = load_data()
    user_id = get_user_id(update)
    
    # Сохраняем кастомное имя
    if "nicknames" not in data["users"][user_id]:
        data["users"][user_id]["nicknames"] = {}
    
    data["users"][user_id]["nicknames"][friend_id] = nickname
    save_data(data)
    
    keyboard = [[InlineKeyboardButton("🖼 Вернуться в галерею", callback_data="gallery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Имя изменено на «{nickname}»!",
        reply_markup=reply_markup
    )


# ============ ДОБАВЛЕНИЕ ДРУГА ============

async def add_friend_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос username друга"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = "friend_username"
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="gallery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👤 *Добавление друга*\n\nВведите username друга (без @):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_friend_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного username"""
    if context.user_data.get("waiting_for") != "friend_username":
        return
    
    context.user_data["waiting_for"] = None
    username = update.message.text.strip().lstrip("@")
    
    data = load_data()
    user_id = get_user_id(update)
    
    # Ищем пользователя по username
    friend_id = None
    for uid, udata in data["users"].items():
        if udata.get("username", "").lower() == username.lower():
            friend_id = uid
            break
    
    if not friend_id:
        await update.message.reply_text(
            f"❌ Пользователь @{username} не найден.\n"
            "Убедитесь, что он уже запустил бота.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gallery")]])
        )
        return
    
    if friend_id == user_id:
        await update.message.reply_text(
            "❌ Нельзя добавить себя в друзья!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gallery")]])
        )
        return
    
    if friend_id in data["users"].get(user_id, {}).get("friends", []):
        await update.message.reply_text(
            f"ℹ️ @{username} уже в вашем списке друзей!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gallery")]])
        )
        return
    
    # Создаем приглашение
    if "invites" not in data:
        data["invites"] = {}
    
    data["invites"][friend_id] = {
        "from_id": user_id,
        "from_username": get_username(update)
    }
    save_data(data)
    
    # Отправляем приглашение другу
    try:
        keyboard = [
            [InlineKeyboardButton("✅ Принять", callback_data=f"accept_invite_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_invite_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=int(friend_id),
            text=f"📨 *Приглашение в галерею*\n\n"
                 f"@{get_username(update)} приглашает вас создать совместную галерею!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ Приглашение отправлено @{username}!\n"
            "Ожидайте ответа.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gallery")]])
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось отправить приглашение. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gallery")]])
        )


# ============ ОБРАБОТКА ПРИГЛАШЕНИЙ ============

async def show_pending_invites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать входящие приглашения"""
    data = load_data()
    user_id = get_user_id(update)
    
    invite = data.get("invites", {}).get(user_id)
    if not invite:
        await show_main_menu(update, context)
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_invite_{invite['from_id']}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_invite_{invite['from_id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📨 *У вас есть приглашение!*\n\n"
        f"@{invite['from_username']} приглашает вас создать совместную галерею!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def accept_invite(update: Update, context: ContextTypes.DEFAULT_TYPE, from_id: str):
    """Принять приглашение"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    
    # Добавляем друг друга в друзья
    if user_id not in data["users"]:
        data["users"][user_id] = {"username": get_username(update), "friends": []}
    if from_id not in data["users"]:
        data["users"][from_id] = {"username": "unknown", "friends": []}
    
    if from_id not in data["users"][user_id].get("friends", []):
        data["users"][user_id].setdefault("friends", []).append(from_id)
    if user_id not in data["users"][from_id].get("friends", []):
        data["users"][from_id].setdefault("friends", []).append(user_id)
    
    # Создаем галерею
    gallery_id = f"{min(user_id, from_id)}_{max(user_id, from_id)}"
    if gallery_id not in data.get("galleries", {}):
        data.setdefault("galleries", {})[gallery_id] = {
            "users": [user_id, from_id],
            "files": []
        }
    
    # Удаляем приглашение
    if user_id in data.get("invites", {}):
        del data["invites"][user_id]
    
    save_data(data)
    
    from_username = data["users"][from_id].get("username", "друг")
    
    await query.edit_message_text(
        f"✅ Вы приняли приглашение!\n\n"
        f"Теперь у вас есть совместная галерея с @{from_username}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🖼 Перейти в галерею", callback_data="gallery")]])
    )
    
    # Уведомляем отправителя
    try:
        await context.bot.send_message(
            chat_id=int(from_id),
            text=f"✅ @{get_username(update)} принял(а) ваше приглашение!\n"
                 f"Теперь у вас есть совместная галерея!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🖼 Перейти в галерею", callback_data="gallery")]])
        )
    except:
        pass


async def decline_invite(update: Update, context: ContextTypes.DEFAULT_TYPE, from_id: str):
    """Отклонить приглашение"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    
    # Удаляем приглашение
    if user_id in data.get("invites", {}):
        del data["invites"][user_id]
        save_data(data)
    
    await query.edit_message_text(
        "❌ Приглашение отклонено.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="main_menu")]])
    )


# ============ ПРОСМОТР ГАЛЕРЕИ ============

async def view_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Просмотр совместной галереи"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    gallery = data.get("galleries", {}).get(gallery_id, {"files": []})
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    
    context.user_data["current_gallery"] = gallery_id
    context.user_data["current_friend"] = friend_id
    
    files = gallery.get("files", [])
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить файл", callback_data=f"add_file_{friend_id}")],
        [InlineKeyboardButton("📦 Экспорт", callback_data=f"export_gallery_{friend_id}")]
    ]
    
    for i, file_info in enumerate(files):
        file_name = file_info.get("name", f"Файл {i+1}")[:20]
        keyboard.append([
            InlineKeyboardButton(f"📄 {file_name}", callback_data=f"show_file_{friend_id}_{i}"),
            InlineKeyboardButton("🗑", callback_data=f"delete_file_{friend_id}_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="gallery")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"� *СовместнаПя галерея с @{friend_name}*\n\n"
    if files:
        text += f"📁 Файлов: {len(files)}"
    else:
        text += "Галерея пуста. Добавьте первый файл!"
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def export_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Экспорт всех файлов галереи"""
    query = update.callback_query
    await query.answer("Начинаю экспорт...")
    
    data = load_data()
    user_id = get_user_id(update)
    
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    gallery = data.get("galleries", {}).get(gallery_id, {"files": []})
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    files = gallery.get("files", [])
    
    if not files:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📭 Галерея пуста, нечего экспортировать."
        )
        return
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📦 *Экспорт галереи с @{friend_name}*\n\n"
             f"Отправляю {len(files)} файлов...",
        parse_mode="Markdown"
    )
    
    sent = 0
    for file_info in files:
        try:
            caption = f"📄 {file_info.get('name', 'Файл')}"
            if file_info.get('added_date'):
                caption += f"\n📅 {file_info['added_date']}"
            if file_info.get('comment'):
                caption += f"\n💬 {file_info['comment']}"
            
            if file_info["type"] == "photo":
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=file_info["file_id"],
                    caption=caption
                )
            elif file_info["type"] == "video":
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file_info["file_id"],
                    caption=caption
                )
            else:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file_info["file_id"],
                    caption=caption
                )
            sent += 1
            await asyncio.sleep(0.5)  # Задержка чтобы не спамить
        except Exception as e:
            save_log(f"Export error: {str(e)[:50]}")
    
    keyboard = [[InlineKeyboardButton("🖼 Вернуться в галерею", callback_data=f"view_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ Экспорт завершён!\nОтправлено файлов: {sent}/{len(files)}",
        reply_markup=reply_markup
    )


# ============ ДОБАВЛЕНИЕ ФАЙЛА ============

async def add_file_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Запрос названия файла"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = "file_name"
    context.user_data["file_friend_id"] = friend_id
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📤 *Добавление файла*\n\n"
        "Введите название для файла (до 25 символов):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_file_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия файла"""
    MAX_NAME_LENGTH = 25
    name = update.message.text.strip()
    friend_id = context.user_data.get("file_friend_id")
    
    if len(name) > MAX_NAME_LENGTH:
        await update.message.reply_text(
            f"❌ Название слишком длинное!\nМаксимум {MAX_NAME_LENGTH} символов, у вас {len(name)}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"add_file_{friend_id}")]])
        )
        context.user_data["waiting_for"] = None
        return
    
    context.user_data["file_name"] = name
    context.user_data["waiting_for"] = "file_comment"
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_comment_{friend_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Название: *{name}*\n\n"
        "Введите комментарий к файлу (до 200 символов) или нажмите «Пропустить»:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_file_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария к файлу"""
    MAX_COMMENT_LENGTH = 200
    comment = update.message.text.strip()
    friend_id = context.user_data.get("file_friend_id")
    
    if len(comment) > MAX_COMMENT_LENGTH:
        await update.message.reply_text(
            f"❌ Комментарий слишком длинный!\nМаксимум {MAX_COMMENT_LENGTH} символов, у вас {len(comment)}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"retry_comment_{friend_id}")],
                [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_comment_{friend_id}")]
            ])
        )
        context.user_data["waiting_for"] = None
        return
    
    context.user_data["file_comment"] = comment
    context.user_data["waiting_for"] = "file"
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Комментарий сохранён!\n\n"
        "Теперь отправьте фото или файл:",
        reply_markup=reply_markup
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженного файла"""
    if context.user_data.get("waiting_for") != "file":
        return
    
    context.user_data["waiting_for"] = None
    friend_id = context.user_data.get("file_friend_id")
    custom_name = context.user_data.get("file_name", "Без названия")
    comment = context.user_data.get("file_comment", "")
    
    if not friend_id:
        return
    
    data = load_data()
    user_id = get_user_id(update)
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    # Определяем тип файла и скачиваем
    import time
    from datetime import datetime
    
    file_info = {}
    file_obj = None
    file_ext = ""
    added_date = datetime.now().strftime("%d.%m.%Y")
    
    if update.message.photo:
        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        file_ext = ".jpg"
        file_info = {
            "type": "photo",
            "file_id": photo.file_id,
            "name": custom_name,
            "comment": comment,
            "added_by": get_username(update),
            "added_date": added_date
        }
    elif update.message.document:
        doc = update.message.document
        file_obj = await context.bot.get_file(doc.file_id)
        file_ext = os.path.splitext(doc.file_name or "")[1] or ".bin"
        file_info = {
            "type": "document",
            "file_id": doc.file_id,
            "name": custom_name,
            "comment": comment,
            "added_by": get_username(update),
            "added_date": added_date
        }
    elif update.message.video:
        video = update.message.video
        file_obj = await context.bot.get_file(video.file_id)
        file_ext = ".mp4"
        file_info = {
            "type": "video",
            "file_id": video.file_id,
            "name": custom_name,
            "comment": comment,
            "added_by": get_username(update),
            "added_date": added_date
        }
    else:
        await update.message.reply_text("❌ Неподдерживаемый тип файла.")
        return
    
    # Сохраняем файл на сервер
    local_filename = f"{gallery_id}_{int(time.time())}{file_ext}"
    local_path = os.path.join(FILES_DIR, local_filename)
    
    try:
        await file_obj.download_to_drive(local_path)
        file_info["local_path"] = local_path
    except Exception as e:
        print(f"Ошибка сохранения файла: {e}")
    
    # Добавляем файл в галерею
    if gallery_id not in data.get("galleries", {}):
        data.setdefault("galleries", {})[gallery_id] = {"users": [user_id, friend_id], "files": []}
    
    data["galleries"][gallery_id]["files"].append(file_info)
    save_data(data)
    
    # Уведомляем друга о новом файле с превью
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    my_username = get_username(update)
    try:
        notify_keyboard = [[InlineKeyboardButton("🖼 Открыть галерею", callback_data=f"view_gallery_{user_id}")]]
        notify_markup = InlineKeyboardMarkup(notify_keyboard)
        
        caption_text = f"📸 @{my_username} добавил(а) новый файл в вашу совместную галерею!\n\n📄 *{custom_name}*"
        if comment:
            caption_text += f"\n💬 {comment}"
        
        # Отправляем файл с уведомлением
        if file_info["type"] == "photo":
            await context.bot.send_photo(
                chat_id=int(friend_id),
                photo=file_info["file_id"],
                caption=caption_text,
                reply_markup=notify_markup,
                parse_mode="Markdown"
            )
        elif file_info["type"] == "video":
            await context.bot.send_video(
                chat_id=int(friend_id),
                video=file_info["file_id"],
                caption=caption_text,
                reply_markup=notify_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_document(
                chat_id=int(friend_id),
                document=file_info["file_id"],
                caption=caption_text,
                reply_markup=notify_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        save_log(f"Notification error: {str(e)[:50]}")
    
    # Очищаем временные данные
    context.user_data.pop("file_comment", None)
    context.user_data.pop("file_name", None)
    
    keyboard = [[InlineKeyboardButton("🖼 Вернуться в галерею", callback_data=f"view_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Файл добавлен в галерею и сохранён на сервере!",
        reply_markup=reply_markup
    )


# ============ ПОКАЗ И УДАЛЕНИЕ ФАЙЛА ============

async def show_file(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str, file_index: int):
    """Показать файл из галереи"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    gallery = data.get("galleries", {}).get(gallery_id, {})
    files = gallery.get("files", [])
    
    if file_index >= len(files):
        await query.answer("Файл не найден", show_alert=True)
        return
    
    file_info = files[file_index]
    keyboard = [
        [InlineKeyboardButton("💬 Добавить комментарий", callback_data=f"add_comment_{friend_id}_{file_index}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"back_to_gallery_{friend_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    added_date = file_info.get('added_date', '')
    caption = f"📄 *{file_info.get('name', 'Файл')}*\n👤 Добавил: @{file_info.get('added_by', 'unknown')}"
    if added_date:
        caption += f"\n📅 Дата: {added_date}"
    
    # Показываем все комментарии
    comments = file_info.get("comments", [])
    if file_info.get("comment"):
        caption += f"\n\n💬 {file_info['comment']}"
    if comments:
        caption += "\n\n📝 *Комментарии:*"
        for c in comments[-5:]:  # Показываем последние 5 комментариев
            caption += f"\n• @{c.get('author', '?')}: {c.get('text', '')}"
    
    try:
        if file_info["type"] == "photo":
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=file_info["file_id"],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        elif file_info["type"] == "video":
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=file_info["file_id"],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_info["file_id"],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        await query.answer(f"Ошибка при загрузке файла", show_alert=True)


async def add_comment_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str, file_index: int):
    """Запрос комментария к файлу"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = "file_new_comment"
    context.user_data["comment_friend_id"] = friend_id
    context.user_data["comment_file_index"] = file_index
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"back_to_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="💬 *Добавление комментария*\n\nВведите ваш комментарий (до 150 символов):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_new_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нового комментария к файлу"""
    MAX_COMMENT_LENGTH = 150
    comment_text = update.message.text.strip()
    friend_id = context.user_data.get("comment_friend_id")
    file_index = context.user_data.get("comment_file_index")
    
    context.user_data["waiting_for"] = None
    
    if len(comment_text) > MAX_COMMENT_LENGTH:
        await update.message.reply_text(
            f"❌ Комментарий слишком длинный!\nМаксимум {MAX_COMMENT_LENGTH} символов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"add_comment_{friend_id}_{file_index}")]])
        )
        return
    
    data = load_data()
    user_id = get_user_id(update)
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    gallery = data.get("galleries", {}).get(gallery_id, {})
    files = gallery.get("files", [])
    
    if file_index >= len(files):
        await update.message.reply_text("❌ Файл не найден.")
        return
    
    # Добавляем комментарий
    if "comments" not in files[file_index]:
        files[file_index]["comments"] = []
    
    files[file_index]["comments"].append({
        "author": get_username(update),
        "text": comment_text
    })
    save_data(data)
    
    keyboard = [[InlineKeyboardButton("🖼 Вернуться в галерею", callback_data=f"view_gallery_{friend_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Комментарий добавлен!",
        reply_markup=reply_markup
    )


async def confirm_delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str, file_index: int):
    """Запрос подтверждения удаления файла"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    gallery = data.get("galleries", {}).get(gallery_id, {})
    files = gallery.get("files", [])
    
    if file_index >= len(files):
        await query.answer("Файл не найден", show_alert=True)
        return
    
    file_info = files[file_index]
    file_name = file_info.get("name", "Файл")
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_del_{friend_id}_{file_index}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🗑 *Удаление файла*\n\n"
        f"Вы уверены, что хотите удалить «{file_name}»?\n"
        f"Это действие нельзя отменить.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str, file_index: int):
    """Удалить файл из галереи"""
    query = update.callback_query
    
    data = load_data()
    user_id = get_user_id(update)
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    gallery = data.get("galleries", {}).get(gallery_id, {})
    files = gallery.get("files", [])
    
    if file_index >= len(files):
        await query.answer("Файл не найден", show_alert=True)
        return
    
    # Удаляем локальный файл если есть
    file_info = files[file_index]
    local_path = file_info.get("local_path")
    if local_path and os.path.exists(local_path):
        try:
            os.remove(local_path)
        except:
            pass
    
    del data["galleries"][gallery_id]["files"][file_index]
    save_data(data)
    
    await query.answer("✅ Файл удален!")
    
    # Обновляем галерею
    await view_gallery(update, context, friend_id)


# ============ НАСТРОЙКИ ============

async def start_chat_request(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Отправить запрос на начало чата"""
    query = update.callback_query
    
    data = load_data()
    user_id = get_user_id(update)
    my_username = get_username(update)
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    
    # Проверяем есть ли уже активная заявка
    existing_request = data.get("chat_requests", {}).get(user_id)
    if existing_request:
        existing_friend_id = existing_request.get("to_id")
        existing_friend_name = data["users"].get(existing_friend_id, {}).get("username", "друг")
        await query.answer(
            f"У вас уже есть активная заявка к @{existing_friend_name}. Сначала отмените её.",
            show_alert=True
        )
        return
    
    # Проверяем есть ли уже активный чат
    if user_id in data.get("active_chats", {}):
        await query.answer("У вас уже есть активный чат. Сначала завершите его.", show_alert=True)
        return
    
    try:
        keyboard = [
            [InlineKeyboardButton("✅ Принять", callback_data=f"accept_chat_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_chat_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        sent_msg = await context.bot.send_message(
            chat_id=int(friend_id),
            text=f"💬 *Запрос на чат*\n\n@{my_username} хочет начать с вами общение!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Сохраняем заявку на чат
        if "chat_requests" not in data:
            data["chat_requests"] = {}
        data["chat_requests"][user_id] = {
            "to_id": friend_id,
            "message_id": sent_msg.message_id
        }
        save_data(data)
        
        await query.answer()
        # Отправляем сообщение о том что заявка отправлена с кнопкой отмены
        keyboard = [[InlineKeyboardButton("❌ Отменить заявку", callback_data=f"cancel_chat_request_{friend_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ Заявка на чат отправлена @{friend_name}!\n\nОжидайте ответа.",
            reply_markup=reply_markup
        )
    except:
        await query.answer("Не удалось отправить запрос", show_alert=True)


async def cancel_chat_request(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Отменить заявку на чат"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    
    # Проверяем есть ли активная заявка
    chat_request = data.get("chat_requests", {}).get(user_id)
    if chat_request and chat_request.get("to_id") == friend_id:
        # Удаляем сообщение у получателя
        try:
            await context.bot.delete_message(
                chat_id=int(friend_id),
                message_id=chat_request["message_id"]
            )
        except:
            pass
        
        # Удаляем заявку
        del data["chat_requests"][user_id]
        save_data(data)
        
        await query.edit_message_text(f"❌ Заявка на чат с @{friend_name} отменена.")
    else:
        await query.edit_message_text("ℹ️ Заявка уже была обработана или отменена.")


async def accept_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, from_id: str):
    """Принять запрос на чат"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    my_username = get_username(update)
    from_username = data["users"].get(from_id, {}).get("username", "друг")
    
    # Удаляем заявку если есть
    if from_id in data.get("chat_requests", {}):
        del data["chat_requests"][from_id]
    
    # Сохраняем активный чат для обоих пользователей
    if "active_chats" not in data:
        data["active_chats"] = {}
    data["active_chats"][user_id] = from_id
    data["active_chats"][from_id] = user_id
    save_data(data)
    
    keyboard = [[InlineKeyboardButton("🚪 Завершить чат", callback_data=f"end_chat_{from_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ Вы приняли запрос на чат от @{from_username}!\n\n"
        f"💬 Чат начат! Просто пишите сообщения — они будут пересылаться собеседнику.\n"
        f"Нажмите кнопку ниже, чтобы завершить чат.",
        reply_markup=reply_markup
    )
    
    # Уведомляем отправителя
    try:
        keyboard = [[InlineKeyboardButton("🚪 Завершить чат", callback_data=f"end_chat_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=int(from_id),
            text=f"🎉 @{my_username} принял(а) вашу заявку на чат!\n\n"
                 f"💬 Чат начат! Просто пишите сообщения — они будут пересылаться собеседнику.\n"
                 f"Нажмите кнопку ниже, чтобы завершить чат.",
            reply_markup=reply_markup
        )
    except:
        pass


async def decline_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, from_id: str):
    """Отклонить запрос на чат"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    from_username = data["users"].get(from_id, {}).get("username", "друг")
    
    # Удаляем заявку если есть
    if from_id in data.get("chat_requests", {}):
        del data["chat_requests"][from_id]
        save_data(data)
    
    await query.edit_message_text(f"❌ Вы отклонили запрос на чат от @{from_username}.")


async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, partner_id: str):
    """Завершить чат"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    my_username = get_username(update)
    partner_username = data["users"].get(partner_id, {}).get("username", "друг")
    
    # Удаляем активный чат
    if "active_chats" in data:
        if user_id in data["active_chats"]:
            del data["active_chats"][user_id]
        if partner_id in data["active_chats"]:
            del data["active_chats"][partner_id]
        save_data(data)
    
    keyboard = [[InlineKeyboardButton("🖼 Перейти в галерею", callback_data="gallery")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🚪 Вы завершили чат с @{partner_username}.",
        reply_markup=reply_markup
    )
    
    # Уведомляем собеседника
    try:
        await context.bot.send_message(
            chat_id=int(partner_id),
            text=f"🚪 @{my_username} завершил(а) чат.",
            reply_markup=reply_markup
        )
    except:
        pass


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработка сообщений в чате. Возвращает True если сообщение обработано."""
    data = load_data()
    user_id = get_user_id(update)
    
    # Проверяем есть ли активный чат
    partner_id = data.get("active_chats", {}).get(user_id)
    if not partner_id:
        return False
    
    my_username = get_username(update)
    
    # Кнопка завершения чата
    keyboard = [[InlineKeyboardButton("🚪 Завершить чат", callback_data=f"end_chat_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Пересылаем текстовое сообщение
        if update.message.text:
            await context.bot.send_message(
                chat_id=int(partner_id),
                text=f"💬 Новое сообщение от @{my_username}!\n\n{update.message.text}",
                reply_markup=reply_markup
            )
        # Пересылаем фото
        elif update.message.photo:
            photo = update.message.photo[-1]
            caption = f"📷 Новое сообщение от @{my_username}!"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_photo(
                chat_id=int(partner_id),
                photo=photo.file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        # Пересылаем видео
        elif update.message.video:
            caption = f"🎥 Новое сообщение от @{my_username}!"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_video(
                chat_id=int(partner_id),
                video=update.message.video.file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        # Пересылаем документы
        elif update.message.document:
            caption = f"📄 Новое сообщение от @{my_username}!"
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            await context.bot.send_document(
                chat_id=int(partner_id),
                document=update.message.document.file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        # Пересылаем голосовые
        elif update.message.voice:
            await context.bot.send_voice(
                chat_id=int(partner_id),
                voice=update.message.voice.file_id,
                caption=f"🎤 Новое сообщение от @{my_username}!",
                reply_markup=reply_markup
            )
        # Пересылаем стикеры
        elif update.message.sticker:
            await context.bot.send_message(
                chat_id=int(partner_id),
                text=f"🎭 Новое сообщение от @{my_username}!",
                reply_markup=reply_markup
            )
            await context.bot.send_sticker(
                chat_id=int(partner_id),
                sticker=update.message.sticker.file_id
            )
        return True
    except Exception as e:
        print(f"Ошибка пересылки сообщения: {e}")
        await update.message.reply_text("❌ Не удалось отправить сообщение собеседнику.")
        return True


async def back_to_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: str):
    """Вернуться в галерею (новое сообщение вместо редактирования фото)"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    
    gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    gallery = data.get("galleries", {}).get(gallery_id, {"files": []})
    friend_name = data["users"].get(friend_id, {}).get("username", "друг")
    
    files = gallery.get("files", [])
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить файл", callback_data=f"add_file_{friend_id}")],
        [
            InlineKeyboardButton("📅⬇️", callback_data=f"sort_gallery_{friend_id}_date_desc"),
            InlineKeyboardButton("�⬆️", callback_data=f"sort_gallery_{friend_id}_date_asc"),
            InlineKeyboardButton("�⬆,️", callback_data=f"sort_gallery_{friend_id}_name_asc"),
            InlineKeyboardButton("🔤⬇️", callback_data=f"sort_gallery_{friend_id}_name_desc")
        ],
        [
            InlineKeyboardButton("👤 Автор", callback_data=f"sort_gallery_{friend_id}_author"),
            InlineKeyboardButton("📋 По умолчанию", callback_data=f"sort_gallery_{friend_id}_default"),
            InlineKeyboardButton("📦 Экспорт", callback_data=f"export_gallery_{friend_id}")
        ]
    ]
    
    for i, file_info in enumerate(files):
        file_name = file_info.get("name", f"Файл {i+1}")[:20]
        keyboard.append([
            InlineKeyboardButton(f"📄 {file_name}", callback_data=f"show_file_{friend_id}_{i}"),
            InlineKeyboardButton("🗑", callback_data=f"delete_file_{friend_id}_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="gallery")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"🖼 *Совместная галерея с @{friend_name}*\n\n"
    if files:
        text += f"📁 Файлов: {len(files)}"
    else:
        text += "Галерея пуста. Добавьте первый файл!"
    
    # Отправляем новое сообщение вместо редактирования (т.к. нельзя редактировать фото в текст)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать настройки со статистикой"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_id = get_user_id(update)
    user_data = data["users"].get(user_id, {})
    friends = user_data.get("friends", [])
    
    # Считаем статистику
    total_media = 0
    media_by_friend = {}
    
    for friend_id in friends:
        gallery_id = f"{min(user_id, friend_id)}_{max(user_id, friend_id)}"
        gallery = data.get("galleries", {}).get(gallery_id, {})
        files = gallery.get("files", [])
        file_count = len(files)
        total_media += file_count
        
        friend_name = data["users"].get(friend_id, {}).get("username", f"user_{friend_id}")
        media_by_friend[friend_name] = file_count
    
    # Находим самого активного друга
    most_active = None
    if media_by_friend:
        most_active = max(media_by_friend.items(), key=lambda x: x[1])
    
    text = f"""⚙️ *Настройки*

👤 Ваш username: @{user_data.get('username', 'не указан')}
🆔 Ваш ID: {user_id}

📊 *Статистика:*
👥 Друзей: {len(friends)}
📁 Всего медиа: {total_media}"""
    
    if most_active and most_active[1] > 0:
        text += f"\n🏆 Самый активный: @{most_active[0]} ({most_active[1]} файлов)"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


# ============ ГЛАВНЫЙ ОБРАБОТЧИК КНОПОК ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех нажатий на кнопки"""
    query = update.callback_query
    data_str = query.data
    
    if data_str == "main_menu":
        await show_main_menu(update, context, edit=True)
    elif data_str == "about":
        await show_about(update, context)
    elif data_str == "gallery":
        await show_gallery_menu(update, context)
    elif data_str == "settings":
        await show_settings(update, context)
    elif data_str == "admin_panel":
        if get_user_id(update) == ADMIN_ID:
            await admin_back(update, context)
    elif data_str == "add_friend":
        await add_friend_prompt(update, context)
    elif data_str.startswith("skip_comment_"):
        friend_id = data_str.replace("skip_comment_", "")
        context.user_data["file_comment"] = ""
        context.user_data["waiting_for"] = "file"
        await query.answer()
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]]
        await query.edit_message_text(
            "Теперь отправьте фото или файл:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data_str.startswith("retry_comment_"):
        friend_id = data_str.replace("retry_comment_", "")
        context.user_data["waiting_for"] = "file_comment"
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_comment_{friend_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"view_gallery_{friend_id}")]
        ]
        await query.edit_message_text(
            "Введите комментарий к файлу (до 200 символов):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data_str.startswith("view_gallery_"):
        friend_id = data_str.replace("view_gallery_", "")
        await view_gallery(update, context, friend_id)
    elif data_str.startswith("export_gallery_"):
        friend_id = data_str.replace("export_gallery_", "")
        await export_gallery(update, context, friend_id)
    elif data_str.startswith("add_file_"):
        friend_id = data_str.replace("add_file_", "")
        await add_file_prompt(update, context, friend_id)
    elif data_str.startswith("show_file_"):
        parts = data_str.replace("show_file_", "").rsplit("_", 1)
        friend_id, file_index = parts[0], int(parts[1])
        await show_file(update, context, friend_id, file_index)
    elif data_str.startswith("add_comment_"):
        parts = data_str.replace("add_comment_", "").rsplit("_", 1)
        friend_id, file_index = parts[0], int(parts[1])
        await add_comment_prompt(update, context, friend_id, file_index)
    elif data_str.startswith("delete_file_"):
        parts = data_str.replace("delete_file_", "").rsplit("_", 1)
        friend_id, file_index = parts[0], int(parts[1])
        await confirm_delete_file(update, context, friend_id, file_index)
    elif data_str.startswith("confirm_del_"):
        parts = data_str.replace("confirm_del_", "").rsplit("_", 1)
        friend_id, file_index = parts[0], int(parts[1])
        await delete_file(update, context, friend_id, file_index)
    elif data_str.startswith("accept_invite_"):
        from_id = data_str.replace("accept_invite_", "")
        await accept_invite(update, context, from_id)
    elif data_str.startswith("decline_invite_"):
        from_id = data_str.replace("decline_invite_", "")
        await decline_invite(update, context, from_id)
    elif data_str.startswith("rename_friend_"):
        friend_id = data_str.replace("rename_friend_", "")
        await rename_friend_prompt(update, context, friend_id)
    elif data_str.startswith("start_chat_"):
        friend_id = data_str.replace("start_chat_", "")
        await start_chat_request(update, context, friend_id)
    elif data_str.startswith("cancel_chat_request_"):
        friend_id = data_str.replace("cancel_chat_request_", "")
        await cancel_chat_request(update, context, friend_id)
    elif data_str.startswith("accept_chat_"):
        from_id = data_str.replace("accept_chat_", "")
        await accept_chat(update, context, from_id)
    elif data_str.startswith("decline_chat_"):
        from_id = data_str.replace("decline_chat_", "")
        await decline_chat(update, context, from_id)
    elif data_str.startswith("back_to_gallery_"):
        friend_id = data_str.replace("back_to_gallery_", "")
        await back_to_gallery(update, context, friend_id)
    elif data_str.startswith("end_chat_"):
        partner_id = data_str.replace("end_chat_", "")
        await end_chat(update, context, partner_id)
    elif data_str == "restart":
        await query.answer()
        # Регистрируем заново
        data = load_data()
        user_id = get_user_id(update)
        data["users"][user_id] = {
            "username": get_username(update),
            "friends": []
        }
        save_data(data)
        await show_main_menu(update, context, edit=True)
    # Админ панель
    elif data_str == "admin_logs":
        if get_user_id(update) == ADMIN_ID:
            await admin_show_logs(update, context)
    elif data_str == "admin_clear_logs":
        if get_user_id(update) == ADMIN_ID:
            await admin_clear_logs(update, context)
    elif data_str == "admin_broadcast":
        if get_user_id(update) == ADMIN_ID:
            await admin_broadcast_prompt(update, context)
    elif data_str == "admin_stats":
        if get_user_id(update) == ADMIN_ID:
            await admin_show_stats(update, context)
    elif data_str == "admin_view_user":
        if get_user_id(update) == ADMIN_ID:
            await admin_view_user_prompt(update, context)
    elif data_str == "admin_ban":
        if get_user_id(update) == ADMIN_ID:
            await admin_ban_prompt(update, context)
    elif data_str.startswith("admin_user_galleries_"):
        if get_user_id(update) == ADMIN_ID:
            target_user_id = data_str.replace("admin_user_galleries_", "")
            await admin_show_user_galleries(update, context, target_user_id)
    elif data_str.startswith("admin_view_gallery_"):
        if get_user_id(update) == ADMIN_ID:
            parts = data_str.replace("admin_view_gallery_", "").split("_")
            await admin_view_user_gallery(update, context, parts[0], parts[1])
    elif data_str.startswith("admin_export_"):
        if get_user_id(update) == ADMIN_ID:
            parts = data_str.replace("admin_export_", "").split("_")
            await admin_export_gallery(update, context, parts[0], parts[1])
    elif data_str == "admin_back":
        if get_user_id(update) == ADMIN_ID:
            await admin_back(update, context)


# ============ ОБРАБОТЧИК ТЕКСТА И ФАЙЛОВ ============

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    # Проверяем админ рассылку
    if await handle_admin_broadcast(update, context):
        return
    
    waiting_for = context.user_data.get("waiting_for")
    
    # Админ команды
    if waiting_for == "admin_view_user" and get_user_id(update) == ADMIN_ID:
        await handle_admin_view_user(update, context)
        return
    elif waiting_for == "admin_ban" and get_user_id(update) == ADMIN_ID:
        await handle_admin_ban(update, context)
        return
    
    # Сначала проверяем waiting_for - приоритет над чатом
    if waiting_for:
        if waiting_for == "friend_username":
            await handle_friend_username(update, context)
            return
        elif waiting_for == "friend_nickname":
            await handle_friend_nickname(update, context)
            return
        elif waiting_for == "file_name":
            await handle_file_name(update, context)
            return
        elif waiting_for == "file_comment":
            await handle_file_comment(update, context)
            return
        elif waiting_for == "file_new_comment":
            await handle_new_comment(update, context)
            return
    
    # Потом проверяем активный чат
    if await handle_chat_message(update, context):
        return


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик файлов"""
    # Проверяем админ рассылку
    if await handle_admin_broadcast(update, context):
        return
    
    # Сначала проверяем waiting_for - приоритет над чатом
    if context.user_data.get("waiting_for") == "file":
        await handle_file(update, context)
        return
    
    # Потом проверяем активный чат
    if await handle_chat_message(update, context):
        return


# ============ АДМИН ПАНЕЛЬ ============

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin - админ панель"""
    user_id = get_user_id(update)
    
    if user_id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👁️ Просмотр по ID", callback_data="admin_view_user")],
        [InlineKeyboardButton("🚫 Бан/Разбан", callback_data="admin_ban")],
        [InlineKeyboardButton("📋 Логи ошибок", callback_data="admin_logs")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔐 *Админ панель*\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def admin_show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать логи ошибок"""
    query = update.callback_query
    await query.answer()
    
    logs = load_logs()
    errors = logs.get("errors", [])
    
    if not errors:
        text = "📋 *Логи ошибок*\n\nОшибок пока нет."
    else:
        text = "📋 *Логи ошибок* (последние 10):\n\n"
        for err in errors[-10:]:
            text += f"[{err['date']}] {err['error'][:100]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить логи", callback_data="admin_clear_logs")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def admin_clear_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить логи"""
    query = update.callback_query
    await query.answer("Логи очищены!")
    
    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"errors": []}, f)
    
    await admin_show_logs(update, context)


async def admin_broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос сообщения для рассылки"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = "admin_broadcast"
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📢 *Рассылка*\n\n"
        "Отправьте сообщение для рассылки.\n"
        "Поддерживается: текст, фото, видео, стикеры.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения для рассылки"""
    user_id = get_user_id(update)
    if user_id != ADMIN_ID:
        return False
    
    if context.user_data.get("waiting_for") != "admin_broadcast":
        return False
    
    context.user_data["waiting_for"] = None
    
    data = load_data()
    users = list(data.get("users", {}).keys())
    
    success = 0
    failed = 0
    
    for uid in users:
        try:
            if update.message.text:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"📢 *Рассылка от администратора:*\n\n{update.message.text}",
                    parse_mode="Markdown"
                )
            elif update.message.photo:
                await context.bot.send_photo(
                    chat_id=int(uid),
                    photo=update.message.photo[-1].file_id,
                    caption=f"📢 *Рассылка от администратора*\n\n{update.message.caption or ''}",
                    parse_mode="Markdown"
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=int(uid),
                    video=update.message.video.file_id,
                    caption=f"📢 *Рассылка от администратора*\n\n{update.message.caption or ''}",
                    parse_mode="Markdown"
                )
            elif update.message.sticker:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text="📢 *Стикер от администратора:*",
                    parse_mode="Markdown"
                )
                await context.bot.send_sticker(
                    chat_id=int(uid),
                    sticker=update.message.sticker.file_id
                )
            success += 1
        except Exception as e:
            failed += 1
            save_log(f"Broadcast to {uid}: {str(e)[:50]}")
    
    keyboard = [[InlineKeyboardButton("◀️ В админ панель", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Успешно: {success}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=reply_markup
    )
    return True


async def admin_show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    
    total_users = len(data.get("users", {}))
    total_galleries = len(data.get("galleries", {}))
    total_files = sum(len(g.get("files", [])) for g in data.get("galleries", {}).values())
    active_chats = len(data.get("active_chats", {})) // 2
    banned_count = len(data.get("banned_users", []))
    
    # Считаем типы файлов
    photos = 0
    videos = 0
    docs = 0
    for g in data.get("galleries", {}).values():
        for f in g.get("files", []):
            if f.get("type") == "photo":
                photos += 1
            elif f.get("type") == "video":
                videos += 1
            else:
                docs += 1
    
    text = f"""📊 *Статистика бота*

👥 *Пользователи:*
├ Всего: {total_users}
└ Забанено: {banned_count}

🖼 *Контент:*
├ Галерей: {total_galleries}
├ Всего файлов: {total_files}
├ 📷 Фото: {photos}
├ 🎥 Видео: {videos}
└ 📄 Документов: {docs}

💬 Активных чатов: {active_chats}"""
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def admin_view_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос ID пользователя для просмотра"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = "admin_view_user"
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👤 *Просмотр пользователя*\n\nВведите ID пользователя:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_admin_view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка просмотра пользователя"""
    user_id_input = update.message.text.strip()
    context.user_data["waiting_for"] = None
    context.user_data["admin_viewing_user"] = user_id_input
    
    data = load_data()
    user_data = data.get("users", {}).get(user_id_input)
    
    if not user_data:
        keyboard = [[InlineKeyboardButton("◀️ В админ панель", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"❌ Пользователь с ID {user_id_input} не найден.",
            reply_markup=reply_markup
        )
        return
    
    username = user_data.get("username", "не указан")
    friends = user_data.get("friends", [])
    is_banned_user = user_id_input in data.get("banned_users", [])
    
    # Считаем файлы пользователя и собираем инфо о друзьях
    total_files = 0
    friends_info = []
    for friend_id in friends:
        gallery_id = f"{min(user_id_input, friend_id)}_{max(user_id_input, friend_id)}"
        gallery = data.get("galleries", {}).get(gallery_id, {})
        files_count = len(gallery.get("files", []))
        total_files += files_count
        
        friend_username = data.get("users", {}).get(friend_id, {}).get("username", "unknown")
        friends_info.append((friend_id, friend_username, files_count))
    
    text = f"""👤 *Информация о пользователе*

🆔 ID: `{user_id_input}`
📛 Username: @{username}
👥 Друзей: {len(friends)}
📁 Файлов в галереях: {total_files}
🚫 Забанен: {'Да' if is_banned_user else 'Нет'}"""
    
    if friends_info:
        text += "\n\n🖼 *Совместные галереи:*"
        for fid, fusername, fcount in friends_info:
            text += f"\n• @{fusername} ({fcount} файлов)"
    
    keyboard = []
    if friends_info:
        keyboard.append([InlineKeyboardButton("📂 Посмотреть галереи", callback_data=f"admin_user_galleries_{user_id_input}")])
    keyboard.append([InlineKeyboardButton("◀️ В админ панель", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def admin_show_user_galleries(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    """Показать галереи пользователя"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    user_data = data.get("users", {}).get(target_user_id, {})
    username = user_data.get("username", "unknown")
    friends = user_data.get("friends", [])
    
    keyboard = []
    for friend_id in friends:
        friend_username = data.get("users", {}).get(friend_id, {}).get("username", "unknown")
        gallery_id = f"{min(target_user_id, friend_id)}_{max(target_user_id, friend_id)}"
        gallery = data.get("galleries", {}).get(gallery_id, {})
        files_count = len(gallery.get("files", []))
        keyboard.append([InlineKeyboardButton(
            f"👤 @{friend_username} ({files_count} файлов)",
            callback_data=f"admin_view_gallery_{target_user_id}_{friend_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📂 *Галереи пользователя @{username}*\n\nВыберите галерею для просмотра:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def admin_view_user_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, user1_id: str, user2_id: str):
    """Просмотр галереи двух пользователей (админ)"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    gallery_id = f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
    gallery = data.get("galleries", {}).get(gallery_id, {"files": []})
    
    user1_name = data.get("users", {}).get(user1_id, {}).get("username", "unknown")
    user2_name = data.get("users", {}).get(user2_id, {}).get("username", "unknown")
    
    files = gallery.get("files", [])
    
    text = f"📂 *Галерея @{user1_name} и @{user2_name}*\n\n"
    text += f"📁 Файлов: {len(files)}\n\n"
    
    if files:
        text += "*Список файлов:*\n"
        for i, f in enumerate(files[:15]):  # Показываем первые 15
            file_type = "📷" if f.get("type") == "photo" else "🎥" if f.get("type") == "video" else "📄"
            text += f"{file_type} {f.get('name', 'Без названия')[:20]}"
            if f.get('added_date'):
                text += f" ({f['added_date']})"
            text += f" - @{f.get('added_by', '?')}\n"
        
        if len(files) > 15:
            text += f"\n... и ещё {len(files) - 15} файлов"
    
    keyboard = [
        [InlineKeyboardButton("📦 Экспорт галереи", callback_data=f"admin_export_{user1_id}_{user2_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"admin_user_galleries_{user1_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def admin_export_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, user1_id: str, user2_id: str):
    """Экспорт галереи (админ)"""
    query = update.callback_query
    await query.answer("Начинаю экспорт...")
    
    data = load_data()
    gallery_id = f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
    gallery = data.get("galleries", {}).get(gallery_id, {"files": []})
    
    user1_name = data.get("users", {}).get(user1_id, {}).get("username", "unknown")
    user2_name = data.get("users", {}).get(user2_id, {}).get("username", "unknown")
    files = gallery.get("files", [])
    
    if not files:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📭 Галерея пуста."
        )
        return
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📦 *Экспорт галереи @{user1_name} и @{user2_name}*\n\nОтправляю {len(files)} файлов...",
        parse_mode="Markdown"
    )
    
    sent = 0
    for file_info in files:
        try:
            caption = f"📄 {file_info.get('name', 'Файл')}\n👤 @{file_info.get('added_by', '?')}"
            if file_info.get('added_date'):
                caption += f"\n📅 {file_info['added_date']}"
            
            if file_info["type"] == "photo":
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_info["file_id"], caption=caption)
            elif file_info["type"] == "video":
                await context.bot.send_video(chat_id=query.message.chat_id, video=file_info["file_id"], caption=caption)
            else:
                await context.bot.send_document(chat_id=query.message.chat_id, document=file_info["file_id"], caption=caption)
            sent += 1
            await asyncio.sleep(0.5)
        except:
            pass
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ Экспорт завершён! Отправлено: {sent}/{len(files)}"
    )


async def admin_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос ID для бана/разбана"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    banned = data.get("banned_users", [])
    
    context.user_data["waiting_for"] = "admin_ban"
    
    text = "🚫 *Бан/Разбан пользователя*\n\nВведите ID пользователя:"
    if banned:
        text += f"\n\n📋 Забанены ({len(banned)}):\n"
        for bid in banned[:10]:
            username = data.get("users", {}).get(bid, {}).get("username", "unknown")
            text += f"• `{bid}` (@{username})\n"
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def handle_admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бана/разбана"""
    user_id_input = update.message.text.strip()
    context.user_data["waiting_for"] = None
    
    data = load_data()
    
    if "banned_users" not in data:
        data["banned_users"] = []
    
    if user_id_input in data["banned_users"]:
        # Разбан
        data["banned_users"].remove(user_id_input)
        save_data(data)
        action = "разбанен ✅"
    else:
        # Бан
        data["banned_users"].append(user_id_input)
        save_data(data)
        action = "забанен 🚫"
    
    username = data.get("users", {}).get(user_id_input, {}).get("username", "unknown")
    
    keyboard = [[InlineKeyboardButton("◀️ В админ панель", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Пользователь `{user_id_input}` (@{username}) {action}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в админ панель"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for"] = None
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👤 Просмотр по ID", callback_data="admin_view_user")],
        [InlineKeyboardButton("🚫 Бан/Разбан", callback_data="admin_ban")],
        [InlineKeyboardButton("📋 Логи ошибок", callback_data="admin_logs")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("◀️ В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔐 *Админ панель*\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============ ЗАПУСК ============

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.VOICE | filters.Sticker.ALL, file_handler))
    
    print("🖼 Бот Галерея запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
