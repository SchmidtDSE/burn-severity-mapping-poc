FROM condaforge/mambaforge

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

# # Get AWS CLI V2
RUN prebuild/setup_aws.sh

# # Get gcloud SDK, force GCP to use IPV4, bc IPV6 issue w/ Sonic 
RUN prebuild/setup_gcloud.sh
ENV PATH $PATH:/usr/local/google-cloud-sdk/bin
ENV GRPC_GO_FORCE_USE_IPV4="true"

# # Get OpenTofu
RUN prebuild/setup_opentofu.sh

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f dev_environment.yml

# # Install nb_conda_kernels in base env to allow for env discovery in jupyter
RUN mamba install -n base nb_conda_kernels

# Start a shell w/ this dev environment - need to keep container running w/ docker-compose
CMD ["tail", "-f", "/dev/null"]
