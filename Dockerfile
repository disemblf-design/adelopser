# Apple Music Downloader — Docker 镜像

FROM python:3.12-slim AS builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gpac \
    ffmpeg \
    bento4 \
    && rm -rf /var/lib/apt/lists/*

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
