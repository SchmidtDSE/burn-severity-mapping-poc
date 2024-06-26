FROM condaforge/mambaforge

# Set noninteractive mode for apt-get, to avoid hanging on tzdata 
ENV DEBIAN_FRONTEND=noninteractive

# Get necessary utils, w/ no-install-recommends and clean up to keep image small
RUN apt-get update && apt-get install -y \
    bash \
    unzip \
    curl \
    ssh \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*  && echo "apt-get install completed"

# Copy necessary files into container
COPY src/ /src/
COPY .deployment/prod_environment.yml /

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f prod_environment.yml && echo "conda env create completed"

# Make 'RUN' use the new environment:
SHELL ["conda", "run", "-n", "burn-severity-prod", "/bin/bash", "-c"]

# Expose port 8080 for the REST API
EXPOSE 8080

# Start the REST API w/ the new environment:
ENTRYPOINT ["conda", "run", "-n", "burn-severity-prod", "uvicorn", "src.app:app", "--host=0.0.0.0", "--port=8080"]