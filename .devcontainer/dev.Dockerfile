# Based on DevPod dev's guidance (Pascal of OpenLoft: https://loft-sh.slack.com/archives/C056ZDZPJ4W/p1720631110300279)
# trying a docker-in-docker setup to allow for docker compose within the container itself
FROM docker:27-dind

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

# Get AWS CLI V2
RUN common/prebuild/setup_aws.sh

# Get gcloud SDK, force GCP to use IPV4, bc IPV6 issue w/ Sonic 
RUN common/prebuild/setup_gcloud.sh
ENV PATH $PATH:/usr/local/google-cloud-sdk/bin
ENV GRPC_GO_FORCE_USE_IPV4="true"

# Get OpenTofu
RUN common/prebuild/setup_opentofu.sh

# Create a new conda environment from the environment.yml file 
WORKDIR /workspace/.devcontainer/burn_backend
RUN mamba env create -f dev_environment.yml

# Install nb_conda_kernels in base env to allow for env discovery in jupyter
RUN mamba install -n base nb_conda_kernels

# Keep the container running
CMD ["tail", "-f", "/dev/null"]