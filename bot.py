import os
import subprocess
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# Путь к вашему основному скрипту (менять не нужно, он в репозитории)
CLI_SCRIPT = "am_downloader/cli.py"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Пришлите ссылку на артиста Apple Music, и я загружу всю дискографию.\n"
        "Пример: /download https://music.apple.com/artist/...\n"
        "После завершения пришлю список ошибок (если будут)."
    )

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите ссылку после /download")
        return
    url = context.args[0]
    await update.message.reply_text(f"⏳ Начинаю загрузку: {url}\nЭто может занять несколько минут...")

    try:
        # Запускаем ваш скрипт
        result = subprocess.run(
            ["python", CLI_SCRIPT, url],
            capture_output=True,
            text=True,
            timeout=600  # 10 минут
        )
        output = result.stdout + result.stderr

        # Ищем в выводе блок "❌ Detailed errors:"
        if "❌ Detailed errors:" in output:
            # Отправляем последние 10 строк с ошибками
            lines = output.splitlines()
            errors = []
            capture = False
            for line in lines:
                if "❌ Detailed errors:" in line:
                    capture = True
                    continue
                if capture and line.strip().startswith((" ", "1.", "2.")):
                    errors.append(line.strip())
                elif capture and not line.strip():
                    break
            if errors:
                await update.message.reply_text("❌ Ошибки при загрузке:\n" + "\n".join(errors[:20]))
            else:
                await update.message.reply_text("✅ Загрузка завершена без ошибок.")
        else:
            await update.message.reply_text("✅ Загрузка завершена. Проверьте логи.")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⚠️ Загрузка заняла слишком много времени, прервано.")
    except Exception as e:
        await update.message.reply_text(f"🔥 Ошибка: {str(e)}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    app.run_polling()

if __name__ == "__main__":
    main()
