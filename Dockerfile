# Apple Music Downloader — Docker 镜像

FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gpac \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -L -o /tmp/bento4.zip https://github.com/nicedayzhu/bento4/releases/download/v1.6.0-641-2-universal/Bento4-SDK-1-6-0-641.2-x86_64-unknown-linux.zip \
    && apt-get purge -y curl && apt-get autoremove -y \
    && cd /tmp && python -m zipfile -e bento4.zip bento4 \
    && cp /tmp/bento4/*/bin/mp4decrypt /usr/local/bin/ \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf /tmp/bento4 /tmp/bento4.zip

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# 复制源码
COPY am_downloader/ ./am_downloader/
COPY cmd/ ./cmd/

# 入口
ENTRYPOINT ["python", "-m", "am_downloader.cli"]
CMD ["--help"]
