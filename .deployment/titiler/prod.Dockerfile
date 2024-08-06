##############
# Base Stage #
##############

FROM condaforge/mambaforge AS base
ARG ENV=PROD

####################
# Environment Stage#
####################

FROM base AS environment
COPY .deployment/titiler/prod_environment.yml /
RUN mamba env create -f prod_environment.yml && echo "conda env create completed"

# This will only install debugpy if env var ENV is LOCAL at docker build time
COPY .devcontainer/scripts/install_debugpy_in_titiler.sh /install_debugpy_in_titiler.sh
RUN ./install_debugpy_in_titiler.sh

####################
# Application Stage
####################

FROM base AS runtime
# Copy the environment from the environment Stage
COPY --from=environment /opt/conda /opt/conda
# Copy application code
COPY src/ /src/

# Make 'RUN' use the new environment
SHELL ["conda", "run", "-n", "titiler-prod", "/bin/bash", "-c"]

# Expose port 8080 for the tileserver
EXPOSE 8080

# Start the REST API with the new environment
ENTRYPOINT ["conda", "run", "-n", "titiler-prod", "uvicorn", "src.titiler.app:app", "--host=0.0.0.0", "--port=8080"]