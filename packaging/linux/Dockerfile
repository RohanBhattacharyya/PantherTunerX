# Build on the oldest supported glibc baseline instead of inheriting a rolling
# host's libc requirements. No application source is copied into this image.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM ubuntu:22.04
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates binutils git rpm desktop-file-utils \
    libegl1 libopengl0 libgl1 libx11-6 libxext6 libxrender1 libxcb1 \
    libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libfontconfig1 libfreetype6 \
    libdbus-1-3 libusb-1.0-0 zlib1g \
    && rm -rf /var/lib/apt/lists/*
ENV UV_CACHE_DIR=/tmp/panther-uv-cache \
    UV_PYTHON_INSTALL_DIR=/tmp/panther-python \
    UV_PROJECT_ENVIRONMENT=/tmp/panther-venv
WORKDIR /work
CMD ["/bin/bash"]
