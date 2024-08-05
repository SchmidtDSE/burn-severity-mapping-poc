##############
# Base Stage #
##############

FROM condaforge/mambaforge AS base
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

COPY .devcontainer/scripts/install_debugpy_in_docker.sh /install_debugpy_in_docker.sh
# This does nothing if env var "ENV" is not "LOCAL"
RUN ./install_debugpy_in_docker.sh

####################
# Application Stage
####################

FROM base AS runtime
COPY --from=environment /opt/conda /opt/conda
COPY src/ /src/
SHELL ["conda", "run", "-n", "burn-severity-prod", "/bin/bash", "-c"]
EXPOSE 5050
ENTRYPOINT ["conda", "run", "-n", "burn-severity-prod", "uvicorn", "src.burn_backend.app:app", "--host=0.0.0.0", "--port=5050"]