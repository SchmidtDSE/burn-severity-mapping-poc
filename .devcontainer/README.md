#### To serve tiles via TiTiler, pointed at S3 url from burn severity backend:

```
http://localhost:8000/cog/map?url=https://burn-severity.s3.us-east-2.amazonaws.com/public/geology/rbr.tif&rescale=-.15,.15
```

## Local Development

### Dev Container

Within the `.devcontainer` directory, there are a few configurations that are used either by the local ![DevPod Client](https://devpod.sh/) or the VS Code `Dev Container` extension.

The former allows you to deploy your dev container to cloud infrastructure without too much hassle, a la GitPod. Both are based on the `devcontainer.json` standard. Either approach will build a Docker container containing the repo itself and its dependencies defined below. Then, VSCode will SSH into that container, treating it as a remote entity, which can be a bit weird at first but is great for reproducibility of your environments across machines!

### Using the DevPod CLI

```
devpod up git@github.com:SchmidtDSE/burn-severity-mapping-poc.git --devcontainer-path .devcontainer/burn_backend/devcontainer.json --ide vscode
```

Useful flags:

- `--devcontainer-path` - path to the devcontainer.json file, which varies depending on the service you're working on.
- `--debug` to get verbose output
- `--recreate` and `--reset` - which will reclone and rebuild the dev container (recreate) and recreate while ignoring cache (reset) respectively. This is useful particuarly when you're updating the devcontainer.json file or relevant build dependencies, and you will want to ensure that your changes work after a --reset before merging anything (since manual changes within the running dev container aren't propogated).

Important files:

- `.devcontainer/[SERVICE]/devcontainer.json` contains some launch configurations, most notably:

  - includes VSCode extensions that are installed **within the container** upon build (your other extensions, most of which will be installed on your 'local' side, should still be there).
  - allows for `postCreateCommands` which allow runtime logic to be performed. The initial iteration of this repo downloaded BARC data on build from a public gcs bucket, but could be anything. This is handled by `.devcontainer/[SERVICE]/init_runtime.sh`, which in turn executes files from `.devcontainer/[SERVICE]/runtime/`.

- `.devcontainer/[SERVICE]/Dockerfile` contains the build instructions for the dev container. Primary responsibilities here are to install necessary linux utilities (bash, curl, etc), setup cloud SDKs/CLIs and OpenTofu to manage those cloud resources, and build a conda environment to manage python dependencies. Note that **this Dockerfile build the dev environment, not the prod environment - so if you need a package to be running in prod, you will add it to the `Dockerfile` found in the root dir as well as this one**.

  - by convention, files in `.devcontainer/[SERVICE]/prebuild` are run here - this means that their effects are baked into the resultant docker image and can take advantage of caching on subsequent runs. This has the benefit of saving time for chunky installs, at the expense of a larger docker image.

- `devcontainer/[SERVICE]/dev_environment.yml` contains the Conda env requirements. As above, **this is just for the dev environment, if you need a package in prod, you must add to the `prod_environment.yaml` in the root dir**.

### Generating Sphinx Docs

```
sphinx-apidoc -o .sphinx/source src
sphinx-build -M html .sphinx/source .sphinx
```

### Debugging w/ VSCode

For local development (inside or outside of a dev container, though the former is recommended), VSCode should detect the launch configuration (`.vscode/launch.json`), allowing for local breakpoints/stepthrough. Port configuration can be found within the same file (default is port `5050`).

### Deploying to Cloud

If you want to deploy to the cloud, you can use OpenTofu to do so - but you need to auth with both `AWS` and `GCP` to do so.

```
aws configure sso
gcloud auth application-default login

```

_Note_: This SSO auth process must be performed periodically, as the authentication token generated are short-lived (important, as the scope of this auth is broad for provisioning resources and could be used by nefarious actors). So, if you run into an credentials-related issue running any `tofu` command, you may need to re-auth. Both will provide you a URL to login via SSO. You can accept all defaults.

### Tofu dotenv generation

TODO: Tofu dotenv (switch to dev or prod)
TODO: 'DEBUG_SERVICE' env var
TODO: Start services with docker compose / attach with debugpy

#### Dev / Prod split

To ensure that we can safely develop in a live environment, without breaking existing functionality, we split dev and prod environments using tofu's `workspace`s.

To select the `prod` environment:

```
tofu workspace select default
```

To select the `dev` environment:

```
tofu workspace select dev
```

By doing this, we avoid having to duplicate tofu source files, such that the deployments are more or less identical between environments.

#### Creating / updating deployments

Once you've selected a workspace and configured sso for both aws and gcloud:

```
tofu init
tofu plan -out .terraform/tfplan
tofu apply ".terraform/tfplan"
```

As alluded to above in the Dev Container section, cloud deployments are pointed to `/prod.Dockerfile` and `/prod_environment.yml` - best practice to avoid the import of dev-related resources here (for eg, most visualization libraries, some pretty printing tools, etc) to keep deployments lighter.
