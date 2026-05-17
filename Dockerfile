FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    gpac \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Скачиваем Bento4 с официального сайта (стабильная ссылка)
RUN wget https://www.bok.net/Bento4/source/Bento4-SRC-1-6-0-641.zip \
    && unzip Bento4-SRC-1-6-0-641.zip \
    && cp Bento4-SRC-1-6-0-641/Build/Targets/x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf Bento4-SRC-1-6-0-641.zip Bento4-SRC-1-6-0-641

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
