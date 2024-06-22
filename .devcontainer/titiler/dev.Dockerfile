### BUILDER ###

FROM condaforge/mambaforge as builder

# Copy repo into container 
COPY . /workspace
WORKDIR /workspace/.devcontainer/titiler

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f dev_environment.yml

### RUNNER ###

FROM builder as runner

# Get the service name from the environment, then set it as an environment variable
ARG DEVCONTAINER_SERVICE
ENV DEVCONTAINER_SERVICE=$DEVCONTAINER_SERVICE
ENV THIS_SERVICE=titiler
RUN echo "DEVCONTAINER_SERVICE: $DEVCONTAINER_SERVICE"

# Expose port 8080 for the tile server
EXPOSE 8080

# Start the proper services - if we aren't developing this service, then start it as uvicorn, otherwise just keep alive
CMD ["/bin/bash", "/workspace/.devcontainer/start_proper_services.sh"]
