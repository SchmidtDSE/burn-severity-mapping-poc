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

# Get AWS CLI V2
RUN ./prebuild/setup_aws.sh

# Get gcloud SDK
RUN ./prebuild/setup_gcloud.sh

# Get OpenTofu
RUN ./prebuild/setup_opentofu.sh

# Copy repo into container 
COPY . .

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f environment.yml

# Install nb_conda_kernels in base env to allow for env discovery in jupyter
RUN mamba install -n base nb_conda_kernels