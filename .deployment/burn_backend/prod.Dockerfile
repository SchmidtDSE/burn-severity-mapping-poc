##############
# Base Stage #
##############

FROM condaforge/mambaforge AS base
ARG ENV=PROD

# Debug logs for docker
ENV PYTHONUNBUFFERED=1

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    bash \
    unzip \
    curl \
    ssh \
    --no-install-recommends && rm -rf /var/lib/apt/lists/* && echo "apt-get install completed"

####################
# Environment Stage#
####################

FROM base AS environment
COPY .deployment/burn_backend/prod_environment.yml /
RUN mamba env create -f prod_environment.yml && echo "conda env create completed"

# This will only install debugpy if env var ENV is LOCAL at docker build time
COPY .devcontainer/scripts/install_debugpy_in_burn_backend.sh /install_debugpy_in_burn_backend.sh
RUN ./install_debugpy_in_burn_backend.sh

####################
# Application Stage
####################

FROM base AS runtime
COPY --from=environment /opt/conda /opt/conda
COPY src/ /src/
SHELL ["conda", "run", "-n", "burn-severity-prod", "/bin/bash", "-c"]
EXPOSE 5050
ENTRYPOINT [ \
    "conda", "run", "-n", "burn-severity-prod", \
    "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "src.burn_backend.app:app", \
    "--bind", "0.0.0.0:5050", \
    "--workers", "1", \
    "--access-logfile", "gunicorn_access.log", \
    "--error-logfile", "gunicorn_error.log", \
    "--log-level", "debug", \
    "--timeout", "0", \
    "--capture-output" \
]