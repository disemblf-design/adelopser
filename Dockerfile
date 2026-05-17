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

# Устанавливаем mp4decrypt (bento4) вручную
RUN wget https://zebradownload.blob.core.windows.net/bento4/bento4-1.6.0-641.x86_64-unknown-linux.zip \
    && unzip bento4-1.6.0-641.x86_64-unknown-linux.zip \
    && cp bento4-1.6.0-641.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf bento4-1.6.0-641.x86_64-unknown-linux.zip bento4-1.6.0-641.x86_64-unknown-linux

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
