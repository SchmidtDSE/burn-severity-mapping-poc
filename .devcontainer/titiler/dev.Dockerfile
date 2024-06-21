FROM condaforge/mambaforge

# Copy repo into container 
COPY . /workspace
WORKDIR /workspace/.devcontainer/titiler

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f dev_environment.yml

# Start a shell w/ this dev environment - need to keep container running w/ docker-compose
CMD ["tail", "-f", "/dev/null"]
