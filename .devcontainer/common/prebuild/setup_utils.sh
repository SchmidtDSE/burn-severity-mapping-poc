#!/bin/bash

apt-get update && apt-get install -y \
    bash \
    unzip \
    curl \
    ca-certificates \
    wget \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*