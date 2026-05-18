FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ffmpeg \
    gpac \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Установка mp4decrypt (Bento4 SDK)
RUN wget https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip \
    && unzip Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip \
    && cp Bento4-SDK-1-6-0-641.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip Bento4-SDK-1-6-0-641.x86_64-unknown-linux

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Устанавливаем сам пакет (совместим с Python 3.11+)
RUN pip install -e .

CMD ["python", "bot.py"]
