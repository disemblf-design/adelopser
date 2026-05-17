FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    gpac \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Скачиваем Bento4 с GitHub (прямая ссылка на релиз)
RUN curl -L https://github.com/axiomatic-systems/Bento4/releases/download/v1.6.0-641/Bento4-1.6.0-641.x86_64-unknown-linux.zip -o bento4.zip \
    && unzip bento4.zip \
    && cp Bento4-1.6.0-641.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf bento4.zip Bento4-1.6.0-641.x86_64-unknown-linux

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
