#### To serve tiles via TiTiler, pointed at S3 url from burn severity backend:

```
http://localhost:8000/cog/map?url=https://burn-severity.s3.us-east-2.amazonaws.com/public/geology/rbr.tif&rescale=-.15,.15
```

## Local Development

### Base Dev Container

To run the repo using the `VSCode - Dev Containers` extension, first ensure you have it installed (along with Docker Desktop), and run:

```
Cmd + Shift + P > Reopen in Dev Container
```

This will take a while on the first pass, but later on, Docker will use cached build images to speed up the process. Just make sure you don't use `Rebuild and Reopen in Container`, which does what it says, unless you really want to.

### Deploying to Cloud

If you want to deploy to the cloud, you can use OpenTofu to do so - but you need to auth with both `AWS` and `GCP`.

```
aws configure sso
gcloud auth application-default login

```

_Note_: This SSO auth process must be performed periodically, as the authentication token generated are short-lived (important, as the scope of this auth is broad for provisioning resources and could be used by nefarious actors). So, if you run into an credentials-related issue running any `tofu` command, you may need to re-auth. Both will provide you a URL to login via SSO. You can accept all defaults.

#### Dev / Prod split

To ensure that we can safely develop in a live environment, without breaking existing functionality, we split dev and prod environments using tofu's `workspace`s.

To select the `prod` or `dev` environment:

```
tofu workspace select prod
tofu workspace select dev
```

By doing this, we avoid having to duplicate tofu source files, such that the deployments are more or less identical between environments.

For local development, you will typically want `dev`, until you are ready to push infrastructure changes to `prod`.

### .env Generation

After initializing with `aws` and `gcp`, you can run the bash script `.devcontainer/scripts/export_tofu_dotenv' to get a valid .env:

```
ENV=LOCAL
DEPLOYMENT=DEV
DEBUG_SERVICE=BURN_BACKEND
S3_FROM_GCP_ROLE_ARN="arn:aws:iam::557418946771:role/aws_s3_from_gcp_dev"
S3_BUCKET_NAME="burn-severity-backend-dev"
GCP_SERVICE_ACCOUNT_S3_EMAIL=burn-backend-service-dev@dse-nps.iam.gserviceaccount.com
GCP_CLOUD_RUN_ENDPOINT_BURN_BACKEND="https://tf-rest-burn-backend-dev-ohi6r6qs2a-uc.a.run.app"
GCP_CLOUD_RUN_ENDPOINT_TITILER="https://tf-titiler-dev-ohi6r6qs2a-uc.a.run.app"
GCP_CLOUD_RUN_ENDPOINT_TITILER_POSSIBLE_ORIGINS="[\"https://tf-titiler-dev-113009620257.us-central1.run.app\",\"https://tf-titiler-dev-ohi6r6qs2a-uc.a.run.app\"]"
```

Note that `DEBUG_SERVICE` can be changed to `TITILER` to attach the VSCode debugger to titiler instead of burn backend.

### Debugging w/ VSCode

You can either run the services in the devcontainer, using the relevant conda environment, or you can run the docker files as they run server side to basically have a 1:1 replication of how the server is running. The former is usefu for development since you don't have to build regularly, but the latter more or less ensures there are no build / runtime issues on the server side that you cannot observe locally.

#### Docker compose workflow

Once you are authenticated with the cloud services and have a valid .env generated, you can can start the services using `docker compose`. Fear not, this is not docker in docker, this is passing the docker daemon through to the dev container. Simply run:

```
docker compose -f .devcontainer/docker-compose.dev.yml build
docker compose -f .devcontainer/docker-compose.dev.yml up

```

For local development (inside or outside of a dev container, though the former is recommended), VSCode should detect the launch configuration (`.vscode/launch.json`), allowing for local breakpoints/stepthrough. Port configuration can be found within the same file (default is port `5050`).

Navigate to the debug panel and select `Attach to Docker Burn Backend`. You should see `Debugger Attached` in the debug console. At this point, you can add breakpoints as you would a locally running application.

#### Just-inside-DevContainer workflow

For this approach, simply run the `Burn Backend FastAPI` launch routine in the debug panel. Everthing should be more or less the same, but in this case you are running the application within the mambaforge image that is the OS for the 'base' dev container, and there are some additional things installed here for development's sake, so it is good to try any major changes using the docker compose based workflow described above before getting ready to merge.

### Cloud Deployment / Maintenance

#### Creating / updating deployments

Once you've selected a workspace and configured sso for both aws and gcloud:

```
tofu init
tofu plan -out .terraform/tfplan
tofu apply ".terraform/tfplan"
```

As alluded to above in the Dev Container section, cloud deployments are pointed to `/prod.Dockerfile` and `/prod_environment.yml` - best practice to avoid the import of dev-related resources here (for eg, most visualization libraries, some pretty printing tools, etc) to keep deployments lighter.

### API documentation

```
sphinx-apidoc -o .sphinx/source src
sphinx-build -M html .sphinx/source .sphinx
```

### Deprecated

### Using the DevPod CLI (Deprecated, for now)

NOTE: Since the cloud-side backend for devpod is not working well for this repo, I recommend using the native `VSCode Dev Containers` extension

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
