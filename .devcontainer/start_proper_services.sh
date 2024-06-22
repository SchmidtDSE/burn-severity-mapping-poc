#!/bin/bash

if [ "$DEVCONTAINER_SERVICE" = "burn_backend" ]; then
    # Start a shell to keep container running
    tail -f /dev/null
else
    # Start the REST API
    conda run -n burn-backend-dev uvicorn src.burn_backend.app:app --host=0.0.0.0 --port=5050
fi

if [ "$DEVCONTAINER_SERVICE" = "titiler" ]; then
    # Start a shell to keep container running
    tail -f /dev/null
else
    # Start the frontend
    conda run -n titiler-dev uvicorn src.titiler.app:app --host=0.0.0.0 --port=8080
fi