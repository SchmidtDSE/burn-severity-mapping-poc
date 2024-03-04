from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from src.routers.check import connectivity, dns, health, sentry_error
from src.routers.analyze import spectral_burn_metrics
from src.routers.upload import drawn_aoi, shapefile_zip
from src.routers.fetch import rangeland_analysis_platform, ecoclass
from src.routers.list import derived_products
from src.routers.pages import home, map, upload, directory
from src.routers.batch import batch_analyze_and_fetch

from src.lib.titiler_algorithms import algorithms

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
add_exception_handlers(app, DEFAULT_STATUS_CODES)
app.mount("/static", StaticFiles(directory="src/static"), name="static")
# templates = Jinja2Templates(directory="src/static")

### WEB PAGES ###
app.include_router(home.router)
app.include_router(map.router)
app.include_router(upload.router)
app.include_router(directory.router)

### CHECK ###
app.include_router(health.router)
app.include_router(sentry_error.router)
app.include_router(connectivity.router)
app.include_router(dns.router)

### ANALYZE ###
app.include_router(spectral_burn_metrics.router)

### UPLOAD ###
app.include_router(drawn_aoi.router)
app.include_router(shapefile_zip.router)

### FETCH ###
app.include_router(rangeland_analysis_platform.router)
app.include_router(ecoclass.router)

### BATCH ###
app.include_router(batch_analyze_and_fetch.router)

### LIST ###
app.include_router(derived_products.router)

### TILESERVER ###
cog = TilerFactory(process_dependency=algorithms.dependency)
app.include_router(cog.router, prefix="/cog", tags=["tileserver"])
