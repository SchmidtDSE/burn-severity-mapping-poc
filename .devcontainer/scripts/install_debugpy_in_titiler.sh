#!/bin/bash

# Run only if env var ENV is LOCAL
if [ "$ENV" != "LOCAL" ]; then
    echo "ENV is not LOCAL. Exiting..."
    exit 0
fi

# Install debugpy in devcontainer-burn_backend
conda install -n titiler-prod debugpy -c conda-forge -y

echo "debugpy installed!"