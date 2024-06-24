### BUILDER ###

FROM condaforge/mambaforge as builder

# Set noninteractive mode for apt-get, to avoid hanging on tzdata
ENV DEBIAN_FRONTEND=noninteractive

# Get necessary utils, w/ no-install-recommends and clean up to keep image small
RUN apt-get update && apt-get install -y \
    bash \
    unzip \
    curl \
    ssh \
    --no-install-recommends && rm -rf /var/lib/apt/lists/* 

# Copy repo into container 
COPY . /workspace
WORKDIR /workspace/.devcontainer

# Get gcloud SDK, force GCP to use IPV4, bc IPV6 issue w/ Sonic 
RUN common/prebuild/setup_gcloud.sh
ENV PATH $PATH:/usr/local/google-cloud-sdk/bin
ENV GRPC_GO_FORCE_USE_IPV4="true"

# Get OpenTofu
RUN common/prebuild/setup_opentofu.sh

# Create a new conda environment from the environment.yml file 
WORKDIR /workspace/.devcontainer/titiler
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
