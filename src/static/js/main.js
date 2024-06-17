class MainPresenter {
  constructor(mapboxToken, cogTileserverUrlPrefix) {
    const self = this;
    self._mapboxToken = mapboxToken;
    self._cogTileserverUrlPrefix = cogTileserverUrlPrefix;

    self._successCounter = 0;
    self._aoiDrawn = false;
    self._shapefileUploaded = false;
    self._geojsonBoundary = null;

    self._locationFormPresenter = new LocationFormPresenter(
      document.querySelector(".location-search"),
      () => self._onLocationChange()
    );

    self._mapPresenter = new MapPresenter("map", () => self._onAoiDrawn());

    self._shapefileFormPresenter = new ShapefileFormPresenter(
      document.querySelector("#shp_zip"),
      () => self._onShapefilesSelected()
    );

    self._fireAnalysisMetaFormPresenter = new FireAnalysisMetaFormPresenter(
      document.querySelector("#fire-analysis-form"),
      () => self._onMetadataSubmit()
    );

    self._productListPresenter = new ProductsListPresenter(
      document.querySelector("#products-list")
    );

    self._mapRbrPresenter = new MapLinkPresenter(
      document.querySelector("#map-rbr"),
      "rbr"
    );

    self._mapDnbrPresenter = new MapLinkPresenter(
      document.querySelector("#map-dnbr"),
      "dnbr"
    );

    self._indicatorArea = new IndicatorAreaPresenter();

    self._apiFacade = new ApiFacade();
  }

  _updateProducts(affiliation, fireEventName) {
    const self = this;

    const derivedProductsResponseFuture = self._apiFacade.getDerivedProducts(
      self._fireAnalysisMetaFormPresenter.getFireEventName(),
      self._fireAnalysisMetaFormPresenter.getAffiliation()
    );

    return derivedProductsResponseFuture.then((products) => {
      self._productListPresenter(products);

      self._mapRbrPresenter.updateUrl(
        self._tileserverEndpoint,
        affiliation,
        fireEventName
      );

      self._mapDnbrPresenter.updateUrl(
        self._tileserverEndpoint,
        affiliation,
        fireEventName
      );
    }, self._makeOnError("Failed to get derived products."));
  }

  _makeOnError(description) {
    const self = this;
    return (error) => {
      console.error(error);
      alert(description);
    };
  }

  _onLocationChange() {
    const self = this;
    const location = self._locationFormPresenter.getLocation();
    self._mapPresenter.goToLocation(location);
  }

  _onAoiDrawn() {
    const self = this;
    self._aoiDrawn = true;
    self._shapefileFormPresenter.disable();
  }

  _onShapefilesSelected() {
    const self = this;

    if (self._shapefileFormPresenter.getFiles().length > 0) {
      self._mapPresenter.removeDrawControl();
    }

    self._shapefileUploaded = true;
  }

  _onMetadataSubmit() {
    const self = this;
    const metadata = self._fireAnalysisMetaFormPresenter.getFormContents();

    const checkState = () =>
      new Promise((resolve, reject) => {
        if (!self._shapefileUploaded && !self._aoiDrawn) {
          alert("Please upload a shapefile or draw an AOI");
          reject();
        } else {
          resolve();
        }
      });

    const checkMetadata = () =>
      new Promise((resolve, reject) => {
        const problems = metadata.getProblems();

        if (problems.length > 0) {
          alert(problems[0]);
          reject();
        } else {
          resolve(metadata);
        }
      });

    const showAllLoading = () => {
      self._indicatorArea.showAllLoading();
    };

    const uploadDrawnAoi = () => {
      const drawnGeojsonStr = self._mapPresenter.getDrawnGeojson();
      return self._apiFacade.uploadDrawnShape(metadata, drawnGeojsonStr);
    };

    const uploadPredefinedAoi = () => {
      const files = self._shapefileFormPresenter.getFiles();
      const file = files[0];
      return self._apiFacade.uploadShapefile(metadata, file);
    };

    const onUploadSuccess = (response) => {
      self._indicatorArea.showUploadSuccess();
      return response;
    };

    const onUploadFail = () => {
      self._indicatorArea.showUploadFail();
    };

    const showAoi = (uploadResponse) => {
      // Get the GeoJSON, either from drawn AOI or uploaded shapefile
      self._geojsonBoundary = JSON.parse(uploadResponse.geojson);

      // Disable editing on the map, and add the drawn/uploaded shape, coloring by whether its final
      self._mapPresenter.disableEditing();
      self._mapPresenter.removeDrawControl();

      // Add the AOI to the map - if we still derive the boundary, then style it red and without fill.
      // We later add the derived boundary to the map, and style it black with fill.
      // Otherwise, style it black and with fill to show its the 'real' boundary.
      self._mapPresenter.showAOI(self._geojsonBoundary, self._aoiDrawn);

      return uploadResponse;
    };

    const analyzeBurn = async (uploadResponse) => {
      const geojson = uploadResponse.geojson;
      const burnAnalysisResponse = await self._apiFacade.analyzeBurn(
        metadata,
        geojson
      );

      return burnAnalysisResponse;
    };

    const showIntermediateBurnMetrics = (burnAnalysisResponse) => {
      const self = this;
      self._indicatorArea.showSatellitePassInfo(burnAnalysisResponse);

      const cloudCogPathRbr = burnAnalysisResponse.getCloudCogPaths().rbr;

      const intermediateProductTileserverUrl =
        self._cogTileserverUrlPrefix + cloudCogPathRbr;

      self._mapPresenter.showIntermediateBurnMetrics(
        intermediateProductTileserverUrl
      );

      self._mapPresenter.enableSeedMetricInput();
      self._indicatorArea.showSeedPointSubmissionWaiting();
    };

    const reportAnalysis = (burnAnalysisResponse) => {
      const self = this;
      return new Promise((resolve, reject) => {
        if (!burnAnalysisResponse.getExecuted()) {
          self._indicatorArea.showBurnAnalysisFailed();
          reject();
          return;
        }

        if (!self._aoiDrawn) {
          // If we didn't draw the AOI, then this is it, we call it a success
          // If not, we use the burn analysis results to derive a boundary
          // before indicating success
          self._indicatorArea.showBurnAnalysisSuccess(burnAnalysisResponse);
        }

        resolve(burnAnalysisResponse);
      });
    };

    const waitForSeedPointSubmission = () => {
      return self._indicatorArea.waitForSeedPointSubmission();
    };

    const refineBurnWithSeedPoints = async () => {
      const geojson = self._mapPresenter.exportEditableLayersAsJson();
      self._indicatorArea.showSeedPointSubmissionPending();
      const refineResponse = await self._apiFacade.refineFloodFill(
        metadata,
        geojson
      );
      return refineResponse;
    };

    const reportRefinement = (refineResponse) => {
      return new Promise((resolve, reject) => {
        if (!refineResponse.getExecuted()) {
          self._indicatorArea.showBurnAnalysisFailed();
          reject();
          return;
        }

        if (!refineResponse.getFireDetected()) {
          self._indicatorArea.showFireNotFound();
          reject();
          return;
        }

        self._indicatorArea.showBurnAnalysisSuccess();

        self._geojsonBoundary = refineResponse.getDerivedBoundary();
        self._mapPresenter.showAOI(self._geojsonBoundary, false);
        self._mapPresenter.removeIntermediateBurnMetrics();

        resolve(refineResponse);
      });
    };

    const performSecondaryAnalysis = () => {
      const ecoclassFuture = self._apiFacade
        .fetchEcoclass(metadata, self._geojsonBoundary)
        .then(
          (x) => {
            self._indicatorArea.showEcoclassSuccess();
            return x;
          },
          () => self._indicatorArea.showEcoclassFailed()
        );

      const rangelandFuture = self._apiFacade
        .fetchRangelandAnalysisPlatform(metadata, self._geojsonBoundary)
        .then(
          (x) => {
            self._indicatorArea.showRangelandSuccess();
            return x;
          },
          () => self._indicatorArea.showRangelandFailed()
        );

      return Promise.all([ecoclassFuture, rangelandFuture]);
    };

    const updateProducts = () => {
      const affiliation = metadata.getAffiliation();
      const fireEventName = metadata.getFireEventName();
      self._updateProducts(affiliation, fireEventName);
    };

    const drawnAoiFlow = () => {
      return checkState()
        .then(checkMetadata)
        .then(showAllLoading)
        .then(uploadDrawnAoi)
        .then(onUploadSuccess)
        .then(showAoi)
        .then(analyzeBurn)
        .then(reportAnalysis)
        .then(showIntermediateBurnMetrics)
        .then(waitForSeedPointSubmission)
        .then(refineBurnWithSeedPoints)
        .then(reportRefinement)
        .then(performSecondaryAnalysis)
        .then(updateProducts);
    };

    const predefinedAoiFlow = () => {
      return checkState()
        .then(checkMetadata)
        .then(showAllLoading)
        .then(uploadPredefinedAoi)
        .then(onUploadSuccess)
        .then(showAoi)
        .then(analyzeBurn)
        .then(reportAnalysis)
        .then(performSecondaryAnalysis)
        .then(updateProducts);
    };

    if (self._aoiDrawn) {
      return drawnAoiFlow();
    } else {
      return predefinedAoiFlow();
    }
  }
}
