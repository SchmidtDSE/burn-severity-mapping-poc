##############
# Base Stage #
##############

FROM condaforge/mambaforge AS base

####################
# Environment Stage#
####################

FROM base AS environment
COPY .deployment/titiler/prod_environment.yml /
RUN mamba env create -f prod_environment.yml && echo "conda env create completed"

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