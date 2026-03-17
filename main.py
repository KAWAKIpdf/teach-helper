import requests, logging, base64, time
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.request import HTTPXRequest

TOKEN = "8573654607:AAEmSfRYg9wvoVfelmKCADZNgha5WV2_wI0"
API_KEY = "sk-HRYbFWj4DTooNSXKd3SR5w66XLa0zbni"
API_URL = "https://routerai.ru/api/v1/chat/completions"
MODEL_NAME = "openai/gpt-5.3-chat"

MAX_HISTORY = 20
MAX_SESSION_TIME = 3600
DEFAULT_TEMP = 0.2
DEFAULT_MAX_TOKENS = 200
OCR_TEMP = 0.1
OCR_MAX_TOKENS = 500
AUTO_CLEAN_COUNT = 20

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_sessions = {}


def main_menu(current_mode=None):
    s = "👨‍🎓 Ученик"
    t = "👩‍🏫 Учитель"
    o = "📸 Распознать текст"
    if current_mode == "student":
        s = "✅ 👨‍🎓 Ученик"
    elif current_mode == "teacher":
        t = "✅ 👩‍🏫 Учитель"
    elif current_mode == "ocr":
        o = "✅ 📸 Распознать текст"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(s, callback_data="mode_student"), InlineKeyboardButton(t, callback_data="mode_teacher")],
        [InlineKeyboardButton(o, callback_data="mode_ocr")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ])


def limit_history(history):
    return history[-MAX_HISTORY:]


def clean_old_sessions():
    c = time.time()
    ex = []
    for uid, sess in user_sessions.items():
        if c - sess.get("last_activity", 0) > MAX_SESSION_TIME:
            ex.append(uid)
    for uid in ex:
        del user_sessions[uid]


def ensure_user(user_id):
    clean_old_sessions()
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "messages": [],
            "temperature": DEFAULT_TEMP,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "mode": None,
            "last_activity": time.time(),
            "message_count": 0
        }
    user_sessions[user_id]["last_activity"] = time.time()
    return user_sessions[user_id]


def get_mode_prompt(mode):
    p = {
        "student": "Ты помощник ученика. Объясняй материал просто и понятно, используй примеры. В конце каждого ответа делай краткий конспект и вывод. Отвечай на русском языке.",
        "teacher": "Ты помощник учителя. Помогай создавать учебные материалы: задания, тесты, планы уроков, методические рекомендации. Давай советы по преподаванию. Отвечай на русском языке.",
        "ocr": "Ты помощник для распознавания текста. Отвечай только на русском языке."
    }
    return p.get(mode, "Ты полезный ассистент. Отвечай на русском языке.")


def check_auto_clean(user_id):
    d = user_sessions[user_id]
    d["message_count"] += 1
    if d["message_count"] >= AUTO_CLEAN_COUNT:
        mode = d.get("mode")
        d["messages"] = []
        d["message_count"] = 0
        if mode:
            d["messages"] = [{"role": "system", "content": get_mode_prompt(mode)}]
        return True
    return False


async def start(update, context):
    uid = str(update.effective_user.id)
    d = ensure_user(uid)
    txt = (
        "✨ *Добро пожаловать в MaxiCO AI!* ✨\n\n"
        "Я ваш универсальный AI-помощник для образования.\n\n"
        "🔹 *Режимы работы:*\n"
        "👨‍🎓 *Ученик* — понятные объяснения, конспекты, помощь в учёбе\n"
        "👩‍🏫 *Учитель* — создание заданий, тестов, планов уроков\n"
        "📸 *Распознавание текста* — извлечение текста из фотографий\n\n"
        "Выберите режим работы и начинайте общение!"
    )
    await update.message.reply_text(txt, reply_markup=main_menu(d.get("mode")), parse_mode="Markdown")


async def button_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = str(q.from_user.id)
    d = ensure_user(uid)
    await q.message.delete()

    if q.data == "mode_student":
        d["mode"] = "student"
        d["temperature"] = DEFAULT_TEMP
        d["max_tokens"] = DEFAULT_MAX_TOKENS
        d["messages"] = [{"role": "system", "content": get_mode_prompt("student")}]
        d["message_count"] = 0
        await context.bot.send_message(chat_id=uid, text=(
            "✅ *Режим Ученик активирован!*\n\n"
            "📝 *Теперь вы можете:*\n"
            "• Задавать вопросы по учёбе\n"
            "• Просить объяснить сложные темы\n"
            "• Получать конспекты и выводы\n\n"
            "✏️ *Напишите свой запрос:*"
        ), reply_markup=main_menu("student"), parse_mode="Markdown")

    elif q.data == "mode_teacher":
        d["mode"] = "teacher"
        d["temperature"] = DEFAULT_TEMP
        d["max_tokens"] = DEFAULT_MAX_TOKENS
        d["messages"] = [{"role": "system", "content": get_mode_prompt("teacher")}]
        d["message_count"] = 0
        await context.bot.send_message(chat_id=uid, text=(
            "✅ *Режим Учитель активирован!*\n\n"
            "📚 *Теперь вы можете:*\n"
            "• Создавать задания и тесты\n"
            "• Разрабатывать планы уроков\n"
            "• Получать методические рекомендации\n\n"
            "✏️ *Напишите свой запрос:*"
        ), reply_markup=main_menu("teacher"), parse_mode="Markdown")

    elif q.data == "mode_ocr":
        d["mode"] = "ocr"
        d["temperature"] = OCR_TEMP
        d["max_tokens"] = OCR_MAX_TOKENS
        d["messages"] = [{"role": "system", "content": get_mode_prompt("ocr")}]
        d["message_count"] = 0
        await context.bot.send_message(chat_id=uid, text=(
            "✅ *Режим распознавания текста активирован!*\n\n"
            "📸 *Отправьте мне фото с текстом,*\n"
            "и я извлеку из него текст."
        ), reply_markup=main_menu("ocr"), parse_mode="Markdown")

    elif q.data == "help":
        await context.bot.send_message(chat_id=uid, text=(
            "❓ *Помощь по использованию*\n\n"
            "🔹 *Режимы работы:*\n"
            "• 👨‍🎓 Ученик - для получения объяснений и помощи в учёбе\n"
            "• 👩‍🏫 Учитель - для создания учебных материалов\n"
            "• 📸 Распознавание текста - извлечение текста из фотографий\n\n"
            "🔹 *Управление:*\n"
            "• /start - перезапустить бота\n"
            "• Меню с кнопками для выбора режима\n\n"
            "🔹 *Особенности:*\n"
            "• История автоматически очищается после 20 сообщений\n"
            "• Сессии автоматически очищаются через 1 час неактивности\n"
            "• При смене режима история автоматически очищается\n\n"
            "✏️ *Просто напишите свой вопрос или отправьте фото после выбора режима!*"
        ), reply_markup=main_menu(d.get("mode")), parse_mode="Markdown")


async def handle_message(update, context):
    uid = str(update.effective_user.id)
    txt = update.message.text
    d = ensure_user(uid)

    if not d.get("mode"):
        await update.message.reply_text(
            "⚠️ *Сначала выберите режим работы!*\n\n"
            "Используйте кнопки меню ниже 👇",
            reply_markup=main_menu(), parse_mode="Markdown"
        )
        return

    if d["mode"] == "ocr":
        await update.message.reply_text(
            "📸 В режиме распознавания текста отправляйте фото, а не текст!",
            reply_markup=main_menu("ocr"), parse_mode="Markdown"
        )
        return

    d["messages"].append({"role": "user", "content": txt})
    d["messages"] = limit_history(d["messages"])

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": MODEL_NAME,
        "messages": d["messages"],
        "temperature": d["temperature"],
        "max_tokens": d["max_tokens"]
    }

    w = await update.message.reply_text("🤔 *Анализирую запрос...*", parse_mode="Markdown")

    try:
        r = requests.post(API_URL, headers=headers, json=data, timeout=60)  # Увеличен таймаут до 60 секунд
        j = r.json()
        if "choices" not in j:
            raise Exception(j.get("error", {}).get("message", str(j)))
        a = j["choices"][0]["message"]["content"]
        d["messages"].append({"role": "assistant", "content": a})

        cl = check_auto_clean(uid)
        reply = f"💡 *Ответ:*\n\n{a}"
        if cl:
            reply += "\n\n🔄 *История автоматически очищена после 20 сообщений*"
        await w.edit_text(reply, reply_markup=main_menu(d.get("mode")), parse_mode="Markdown")

    except requests.exceptions.Timeout:
        await w.edit_text(
            "⏰ *Превышено время ожидания ответа от API.*\n\n"
            "Пожалуйста, попробуйте еще раз через несколько секунд.",
            reply_markup=main_menu(d.get("mode")), parse_mode="Markdown"
        )
    except Exception as e:
        await w.edit_text(
            f"❌ *Произошла ошибка:*\n\n`{str(e)}`\n\n"
            "Пожалуйста, попробуйте еще раз или выберите другой режим.",
            reply_markup=main_menu(d.get("mode")), parse_mode="Markdown"
        )


async def handle_photo(update, context):
    uid = str(update.effective_user.id)
    d = ensure_user(uid)

    if d.get("mode") != "ocr":
        await update.message.reply_text(
            "⚠️ *Сначала выберите режим распознавания текста!*\n\n"
            "Нажмите кнопку '📸 Распознать текст' в меню ниже 👇",
            reply_markup=main_menu(d.get("mode")), parse_mode="Markdown"
        )
        return

    w = await update.message.reply_text("📥 *Загружаю изображение...*", parse_mode="Markdown")

    try:
        p = update.message.photo[-1]
        f = await context.bot.get_file(p.file_id)
        b = await f.download_as_bytearray()

        await w.edit_text("🔧 *Обрабатываю изображение...*", parse_mode="Markdown")

        img = Image.open(BytesIO(b))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if max(img.size) > 1024:
            r = 1024 / max(img.size)
            img = img.resize((int(img.size[0] * r), int(img.size[1] * r)), Image.Resampling.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()

        await w.edit_text("🔍 *Распознаю текст...*", parse_mode="Markdown")

        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL_NAME,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Распознай текст на изображении. Только текст, без пояснений."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }],
            "temperature": d["temperature"],
            "max_tokens": d["max_tokens"]
        }

        if d["messages"]:
            payload["messages"] = d["messages"] + payload["messages"]

        r = requests.post(API_URL, headers=headers, json=payload, timeout=60)  # Увеличен таймаут до 60 секунд
        j = r.json()

        if "choices" not in j:
            raise Exception(j.get("error", {}).get("message", str(j)))

        text = j["choices"][0]["message"]["content"].strip()

        d["messages"].append({"role": "user", "content": "[Фото]"})
        d["messages"].append({"role": "assistant", "content": text})
        if len(d["messages"]) > MAX_HISTORY * 2:
            d["messages"] = d["messages"][-MAX_HISTORY * 2:]

        cl = check_auto_clean(uid)

        if len(text) > 4000:
            await w.delete()
            for i in range(0, len(text), 4000):
                await update.message.reply_text(
                    f"{text[i:i + 4000]}",
                    reply_markup=main_menu("ocr") if i == 0 else None
                )
        else:
            reply = f"📝 *Распознанный текст:*\n\n{text}"
            if cl:
                reply += "\n\n🔄 *История автоматически очищена после 20 сообщений*"
            await w.edit_text(reply, reply_markup=main_menu("ocr"), parse_mode="Markdown")

    except requests.exceptions.Timeout:
        await w.edit_text(
            "⏰ *Превышено время ожидания ответа от API.*\n\n"
            "Пожалуйста, попробуйте еще раз.",
            reply_markup=main_menu("ocr"), parse_mode="Markdown"
        )
    except Exception as e:
        await w.edit_text(
            f"❌ *Ошибка распознавания:*\n\n`{str(e)[:200]}`",
            reply_markup=main_menu("ocr"), parse_mode="Markdown"
        )


def main():
    try:
        # Создаем кастомный request с увеличенными таймаутами
        request = HTTPXRequest(
            connection_pool_size=20,
            read_timeout=60.0,  # Увеличен до 60 секунд
            write_timeout=60.0,  # Увеличен до 60 секунд
            connect_timeout=60.0,  # Увеличен до 60 секунд
            pool_timeout=60.0  # Увеличен до 60 секунд
        )

        # Создаем приложение с кастомным request
        app = ApplicationBuilder().token(TOKEN).request(request).build()

        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        print("🤖 Бот запускается с увеличенными таймаутами (60 секунд)...")
        print("⚡ Ожидание сообщений...")

        # Запускаем polling с увеличенными параметрами
        app.run_polling(
            drop_pending_updates=True,
            poll_interval=0.5,
            timeout=60,  # Увеличен до 60 секунд
            read_timeout=60,  # Увеличен до 60 секунд
            write_timeout=60,  # Увеличен до 60 секунд
            connect_timeout=60,  # Увеличен до 60 секунд
            pool_timeout=60  # Увеличен до 60 секунд
        )

    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("\n💡 Проверьте:")
        print("1. Подключение к интернету")
        print("2. Токен бота")
        print("3. Доступность Telegram (api.telegram.org)")


if __name__ == "__main__":
    main()