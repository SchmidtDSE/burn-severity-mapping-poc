FROM condaforge/mambaforge

# Copy necessary files into container
COPY src/ /src/
COPY .deployment/titiler/prod_environment.yml /

# Create a new conda environment from the environment.yml file 
RUN mamba env create -f prod_environment.yml && echo "conda env create completed"

# Make 'RUN' use the new environment:
SHELL ["conda", "run", "-n", "titiler-prod", "/bin/bash", "-c"]

# Expose port 8080 for the tileserver
EXPOSE 8080

# Start the REST API w/ the new environment:
ENTRYPOINT ["conda", "run", "-n", "titiler-prod", "uvicorn", "src.titiler.app:app", "--host=0.0.0.0", "--port=8080"]