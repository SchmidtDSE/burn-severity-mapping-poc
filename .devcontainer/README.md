#### To serve tiles via TiTiler, pointed at S3 url from burn severity backend:
```
http://localhost:8000/cog/map?url=https://burn-severity.s3.us-east-2.amazonaws.com/public/geology/rbr.tif&rescale=-.15,.15
```

## Local Development

### Dev Container

Within the `.devcontainer` directory, there are a few configurations that are used either by the local ![DevPod Client](https://devpod.sh/) or the VS Code `Dev Container` extension. 

The former allows you to deploy your dev container to cloud infrastructure without too much hassle, a la GitPod. Both are based on the `devcontainer.json` standard. Either approach will build a Docker container containing the repo itself and its dependencies defined below. Then, VSCode will SSH into that container, treating it as a remote entity, which can be a bit weird at first but is great for reproducibility of your environments across machines!

- `.devcontainer/devcontainer.json` contains some launch configurations, most notably:
    - includes VSCode extensions that are installed **within the container** upon build (your other extensions, most of which will be installed on your 'local' side, should still be there).
    - allows for `postCreateCommands` which allow runtime logic to be performed. The initial iteration of this repo downloaded BARC data on build from a public gcs bucket, but could be anything. This is handled by `.devcontainer/init_runtime.sh`, which in turn executes files from `.devcontainer/runtime/`. 

- `.devcontainer/Dockerfile` contains the build instructions for the dev container. Primary responsibilities here are to install necessary linux utilities (bash, curl, etc), setup cloud SDKs/CLIs and OpenTofu to manage those cloud resources, and build a conda environment to manage python dependencies. Note that **this Dockerfile build the dev environment, not the prod environment - so if you need a package to be running in prod, you will add it to the `Dockerfile` found in the root dir as well as this one**. 
    - by convention, files in `.devcontainer/prebuild` are run here - this means that their effects are baked into the resultant docker image and can take advantage of caching on subsequent runs. This has the benefit of saving time for chunky installs, at the expense of a larger docker image.

- `devcontainer/dev_environment.yml` contains the Conda env requirements. As above, **this is just for the dev environment, if you need a package in prod, you must add to the `prod_environment.yaml` in the root dir**. 

### Debugging w/ VSCode

For local development (inside or outside of a dev container, though the former is recommended), VSCode should detect the launch configuration (`.vscode/launch.json`), allowing for local breakpoints/stepthrough. Port configuration can be found within the same file (default is port `5050`).

### Deploying to Cloud 

If you want to deploy to the cloud, you can use OpenTofu to do so - but you need to auth with both `AWS` and `GCP` to do so. 
```
aws configure sso
gcloud auth application-default login

```

*Note*: This SSO auth process must be performed peridically, as the authentication token generated are short-lived (important, as the scope of this auth is broad for provisioning resources and could be used by nefarious actors). So, if you run into an credentials-related issue running any `tofu` command, you may need to re-auth. Both will provide you a URL to login via SSO. You can accept all defaults. 

Once this is done, run:

```
tofu init
tofu plan -out .terraform/tfplan
tofu apply ".terraform/tfplan"
```

As alluded to above in the Dev Container section, cloud deployments are pointed to `/prod.Dockerfile` and `/prod_environment.yml` - best practice to avoid the import of dev-related resources here (for eg, most visualization libraries, some pretty printing tools, etc) to keep deployments lighter. 

## Dev ToDo

- Investigate DevPod's ability to deploy a browser-based instance of VSCode - if not, can we simply spin one up on a VM to emulate gitpod?

- Investigate deploying DevPod to remote cloud providers (very very briefly attempted this but ran into a network issue, see below)

- Address IPv4 issues with opentofu deployment / state refresh (this is a Nick's house specific issue with Sonic ISP)

- Store OpenTofu state in remote bucket (best practice to avoid multiple state files from being out of sync)

- Validate Cloud Build workflow on Dev branch

- Implement basic branch protections

- VSCode inside dev container doesn't properly launch web broswer for SSO auth

- Catalog any/all analytical products with Source Coop

- Sphinx to auto generate docs from docstrings

- Look into more platform agnostic secrets management (more so for DSE in general)
    - Pass w/ tofu on deployment?
    - Use vault-style, a la 1Password?
