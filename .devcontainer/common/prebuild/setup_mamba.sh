#!/bin/bash

# Ensure the script exits if any command fails
set -e

# Download and install Mambaforge version 24.3.0-0 (just a stable version)
wget -qO- https://github.com/conda-forge/miniforge/releases/download/24.3.0-0/Mambaforge-Linux-x86_64.sh 

# Make it executable
chmod +x Mambaforge-Linux-x86_64.sh

# Run the downloaded script
bash ./Mambaforge-Linux-x86_64.sh -b -p /opt/mambaforge

# Add Mambaforge to PATH
echo 'export PATH=/opt/mambaforge/bin:$PATH' >>~/.profile

# Clean up
rm -rf /var/cache/apk/*