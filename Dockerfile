FROM ubuntu:22.04

# Принудительно задаём DNS-серверы Google (решает проблему с DNS внутри контейнера)
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf
RUN echo "nameserver 8.8.4.4" >> /etc/resolv.conf

ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем Python 3.11 из deadsnakes PPA
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && apt-get install -y \
    python3.11 \
    python3.11-distutils \
    python3.11-dev \
    ffmpeg \
    gpac \
    wget \
    unzip \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем pip для Python 3.11
RUN wget https://bootstrap.pypa.io/get-pip.py && python3 get-pip.py && rm get-pip.py

# Устанавливаем mp4decrypt (Bento4 SDK)
RUN wget https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip \
    && unzip Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip \
    && cp Bento4-SDK-1-6-0-641.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip Bento4-SDK-1-6-0-641.x86_64-unknown-linux

WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python3 -m pip install -e .

CMD ["python3", "bot.py"]
