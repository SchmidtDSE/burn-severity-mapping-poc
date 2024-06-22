from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


from src.burn_backend.routers.check import connectivity, dns, health, sentry_error
from src.burn_backend.routers.analyze import spectral_burn_metrics
from src.burn_backend.routers.refine import flood_fill_segmentation
from src.burn_backend.routers.upload import drawn_aoi, shapefile_zip
from src.burn_backend.routers.fetch import rangeland_analysis_platform, ecoclass
from src.burn_backend.routers.list import derived_products
from src.burn_backend.routers.pages import home, map, upload, directory
from src.burn_backend.routers.batch import batch_analyze_and_fetch

## APP SETUP ##
app = FastAPI(docs_url="/documentation")
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

### REFINE ###
app.include_router(flood_fill_segmentation.router)

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

### HEALTHCHECK ###
@app.get("/healthz", tags=["healthcheck"])
def ping():
    """Health check."""
    return {"ping": "pong!"}