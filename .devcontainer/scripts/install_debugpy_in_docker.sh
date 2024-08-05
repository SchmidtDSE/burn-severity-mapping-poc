#!/bin/bash

# Run only if env var ENV is LOCAL
if [ "$ENV" != "LOCAL" ]; then
    echo "ENV is not LOCAL. Exiting..."
    exit 0
fi

# Install debugpy in devcontainer-burn_backend
docker exec devcontainer-burn_backend-1 conda install -n burn-severity-prod debugpy -c conda-forge debugpy -y

# Install debugpy in devcontainer-titiler
docker exec devcontainer-titiler-1 conda install -n titiler-prod debugpy -c conda-forge debugpy -y

echo "debugpy installed in both containers."