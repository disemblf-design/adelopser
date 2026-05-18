import os
import subprocess
from telegram.ext import Updater, CommandHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def start(update, context):
    update.message.reply_text("Отправь /download со ссылкой на артиста Apple Music")

def download(update, context):
    if not context.args:
        update.message.reply_text("Укажите ссылку после /download")
        return
    url = context.args[0]
    update.message.reply_text(f"⏳ Загружаю {url}... (лог будет в Telegram)")

    try:
        result = subprocess.run(
            ["python", "am_downloader/cli.py", url],
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy()
        )
        output = result.stdout + "\n" + result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n... (обрезано)"
        update.message.reply_text(f"Код возврата: {result.returncode}\n\nВывод:\n{output}")
    except subprocess.TimeoutExpired:
        update.message.reply_text("⚠️ Загрузка заняла слишком много времени, прервано.")
    except Exception as e:
        update.message.reply_text(f"🔥 Ошибка: {str(e)}")

def main():
    if not TOKEN:
        print("Токен не задан")
        return
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("download", download))
    updater.start_polling()
    print("Бот запущен")
    updater.idle()

if __name__ == "__main__":
    main()
