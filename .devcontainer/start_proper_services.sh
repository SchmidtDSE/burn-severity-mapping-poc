#!/bin/bash

cd /workspace
echo "Starting other services to develop with ${DEVCONTAINER_SERVICE}..."

if [ "$DEVCONTAINER_SERVICE" = "$THIS_SERVICE" ]; then
    # Start a shell to keep container running
    tail -f /dev/null
else
    if [ "$THIS_SERVICE" = "titiler" ]; then
        # Start the frontend
        conda run -n titiler-dev uvicorn src.titiler.app:app --host=0.0.0.0 --port=8080
    fi

    if [ "$THIS_SERVICE" = "burn_backend" ]; then
        # Start the REST API
        conda run -n burn-backend-dev uvicorn src.burn_backend.app:app --host=0.0.0.0 --port=5050
    fi
fi