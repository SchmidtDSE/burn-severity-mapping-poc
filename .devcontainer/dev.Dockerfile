# Based on DevPod dev's guidance (Pascal of OpenLoft: https://loft-sh.slack.com/archives/C056ZDZPJ4W/p1720631110300279)
# trying a docker-in-docker setup to allow for docker compose within the container itself
FROM condaforge/mambaforge as builder

# Copy repo into container 
COPY . /workspace
WORKDIR /workspace/.devcontainer

#########################
### BASE REQUIREMENTS ###
#########################

# Make debian non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Get necessary utils
RUN common/prebuild/setup_utils.sh

# Get docker and it dependencies
RUN common/prebuild/setup_docker.sh

##############################
### ENVIRONMENT MANAGEMENT ###
##############################

# Create the burn-backend-dev's conda environment
RUN mamba env create -f burn_backend/dev_environment.yml

# Create the titiler-dev's conda environment
RUN mamba env create -f titiler/dev_environment.yml

# Install nb_conda_kernels in base env to allow for env discovery in jupyter
# Ensure mamba or conda is installed and available in the image before running this
RUN mamba install -n base nb_conda_kernels

################################
### DEVELOPMENT REQUIREMENTS ###
################################

# Get AWS CLI V2
RUN common/prebuild/setup_aws.sh

# Get gcloud SDK, force GCP to use IPV4, bc IPV6 issue w/ Sonic 
RUN common/prebuild/setup_gcloud.sh
ENV PATH $PATH:/usr/local/google-cloud-sdk/bin
ENV GRPC_GO_FORCE_USE_IPV4="true"

# Get OpenTofu
RUN common/prebuild/setup_opentofu.sh

#########################
### RUNTIME KEEP-ALIVE###
#########################

# Keep the container running
CMD ["tail", "-f", "/dev/null"]