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

# Get AWS CLI
RUN pip3 --no-cache-dir install --upgrade awscli

# Copy repo into 
COPY . .

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f environment.yml

# Make 'RUN' use the new environment:
SHELL ["conda", "run", "-n", "burn-severity-prod", "/bin/bash", "-c"]

# Expose port 5000 for the REST API
EXPOSE 5000

# Start the REST API w/ the new environment:
ENTRYPOINT ["conda", "run", "-n", "burn-severity-prod", "python", "main.py"]