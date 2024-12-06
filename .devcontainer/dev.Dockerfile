# Based on DevPod dev's guidance (Pascal of OpenLoft: https://loft-sh.slack.com/archives/C056ZDZPJ4W/p1720631110300279)
# trying a docker-in-docker setup to allow for docker compose within the container itself
FROM condaforge/mambaforge AS base

# Copy repo into container 
COPY . /workspace
WORKDIR /workspace

#########################
### BASE REQUIREMENTS ###
#########################

# Make debian non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Get necessary utils
RUN .devcontainer/prebuild/setup_utils.sh

# Get docker and it dependencies
RUN .devcontainer/prebuild/setup_docker.sh

################################
### DEVELOPMENT REQUIREMENTS ###
################################

# Get AWS CLI V2
RUN .devcontainer/prebuild/setup_aws.sh

# Get gcloud SDK, force GCP to use IPV4, bc IPV6 issue w/ Sonic
RUN .devcontainer/prebuild/setup_gcloud.sh
ENV PATH=$PATH:/usr/local/google-cloud-sdk/bin
ENV GRPC_GO_FORCE_USE_IPV4="true"

# Get OpenTofu
RUN .devcontainer/prebuild/setup_opentofu.sh

##############################
### ENVIRONMENT MANAGEMENT ###
##############################

FROM base AS environment

WORKDIR /workspace

# Create the burn-backend-prods's conda environment and add our common dev environment addons
RUN mamba env create -f .deployment/burn_backend/prod_environment.yml
RUN mamba env update -f .devcontainer/dev_environment_addons.yml -n burn-severity-prod

# Create the titiler-prod's conda environment and add our common dev environment addons
RUN mamba env create -f .deployment/titiler/prod_environment.yml
RUN mamba env update -f .devcontainer/dev_environment_addons.yml -n titiler-prod

# Install nb_conda_kernels in base env to allow for env discovery in jupyter
RUN mamba install -n base nb_conda_kernels

# Install pixi in base env to allow VSCode to properly use conda env for tests extension
RUN mamba install -n base pixi

#########################
### RUNTIME KEEP-ALIVE###
#########################

FROM base AS runtime

# Copy the conda environment from the environment stage
COPY --from=environment /opt/conda /opt/conda

# Keep the container running 
CMD ["tail", "-f", "/dev/null"]