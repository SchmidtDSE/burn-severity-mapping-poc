const AnalysisStatus = {
  PENDING: "pending",
  SUCCESS: "success",
  FAILURE: "failure",
};

class MapPresenter {
  constructor(targetId, onAoiDrawn) {
    const self = this;

    const map = L.map(targetId).setView([39.7749, -100.4194], 5);

    // Create panes to properly order basemaps and boundaries
    map.createPane("basemaps");
    map.getPane("basemaps").style.zIndex = 2;

    map.createPane("intermediateBurnMetrics");
    map.getPane("intermediateBurnMetrics").style.zIndex = 3;

    map.createPane("boundary");
    map.getPane("boundary").style.zIndex = 5;

    // // Add a tile layer to the map
    // L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    //   maxZoom: 19,
    //   attribution: "© OpenStreetMap contributors",
    //   pane: "basemaps",
    // }).addTo(map);

    // Add a tile layer to the map
    L.tileLayer(
      `https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/tiles/{z}/{x}/{y}?access_token=${mapboxToken}`,
      {
        maxZoom: 19,
        attribution: "© Mapbox",
        pane: "basemaps",
        tileSize: 512,
        zoomOffset: -1,
      }
    ).addTo(map);

    // Initialize the FeatureGroup to store editable layers
    const { editableLayers, drawControl } = this.addDrawControl(
      map,
      onAoiDrawn,
      {
        polyline: false,
        marker: false,
        circle: false,
        circlemarker: false,
        rectangle: true,
        polygon: true,
      }
    );

    self._innerMap = map;
    self._editableLayers = editableLayers;
    self._drawControl = drawControl;
    self._aoiControl = null;
  }

  addDrawControl(map, drawCallback, drawOptions = {}) {
    const editableLayers = new L.FeatureGroup();
    map.addLayer(editableLayers);

    // Initialize the draw control and pass it the FeatureGroup of editable layers
    const drawControl = new L.Control.Draw({
      draw: drawOptions,
      edit: {
        featureGroup: editableLayers,
      },
    });
    map.addControl(drawControl);

    map.on("draw:created", (e) => {
      var type = e.layerType,
        layer = e.layer;

      // Add the drawn layer to the editable layers
      editableLayers.addLayer(layer);

      drawCallback(e);
    });

    return { editableLayers, drawControl };
  }

  removeDrawControl() {
    const self = this;
    self._innerMap.removeControl(self._drawControl);
  }

  goToLocation(location) {
    const self = this;
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${location}`;
    fetch(url)
      .then(get200Json)
      .then((data) => {
        if (data.length > 0) {
          self._innerMap.setView([data[0].lat, data[0].lon], 13);
        } else {
          alert("Location not found");
        }
      });
  }

  getDrawnGeojson() {
    const self = this;
    return JSON.stringify(self._editableLayers.toGeoJSON());
  }

  disableEditing() {
    const self = this;

    self._editableLayers.eachLayer((layer) => {
      self._editableLayers.removeLayer(layer);
    });

    self._editableLayers = null;
  }

  showAOI(aoi, deriveBoundary) {
    const self = this;

    const uploadedLayer = L.geoJSON(aoi, {
      style: function () {
        return {
          color: deriveBoundary ? "#f12215" : "#000000",
          weight: 2,
          opacity: 1,
          fillOpacity: deriveBoundary ? 0 : 0.5,
        };
      },
      pane: "boundary",
    }).addTo(self._innerMap);

    // Center the uploaded layer on the map
    self._innerMap.fitBounds(uploadedLayer.getBounds());

    const aoiLabel = deriveBoundary ? "Approximate AOI" : "Predefined Boundary";

    const control = L.control.layers(
      null,
      {
        aoiLabel: uploadedLayer,
      },
      { collapsed: false }
    );

    self._aoiControl = control;
  }

  showBoundaryGeojson(boundaryGeojson) {
    const self = this;

    var boundaryParsed = JSON.parse(boundaryGeojson);

    try {
      console.log("adding derived boundary to map");
      var derivedLayer = L.geoJSON(boundaryParsed, {
        style: {
          color: "#000000",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.5,
        },
        pane: "boundary",
      }).addTo(self._innerMap);

      console.log("adding derived layer control to map");
      var control = L.control.layers(
        null,
        {
          "Approximate AOI": uploadedLayer,
          "Derived Boundary": derivedLayer,
        },
        { collapsed: false }
      );
      control.addTo(self._innerMap);
    } catch (error) {
      console.error(error);
    }
  }

  showIntermediateBurnMetrics(burnMetricHttpPath) {
    const self = this;

    // Create a new tile layer with the provided URL
    const metricLayer = L.tileLayer(burnMetricHttpPath, {
      maxZoom: 19,
      pane: "intermediateBurnMetrics",
    });

    // Add the new layer to the map
    metricLayer.addTo(self._innerMap);
  }

  enableSeedMetricInput() {
    const self = this;

    const onSeedPointDrawn = (e) => {
      const lat = e.layer._latlng.lat;
      const lon = e.layer._latlng.lng;
      const seedPoint = [lat, lon];
      console.log(seedPoint);
    };

    const { editableLayers, drawControl } = this.addDrawControl(
      self._innerMap,
      onSeedPointDrawn,
      {
        polyline: false,
        marker: true,
        circle: false,
        circlemarker: false,
        rectangle: false,
        polygon: false,
      }
    );

    self._editableLayers = editableLayers;
    self._drawControl = drawControl;
  }

  exportEditableLayersAsJson() {
    const self = this;
    return self._editableLayers.toGeoJSON();
  }
}

class LocationFormPresenter {
  constructor(selection, onLocationChange) {
    const self = this;
    self._selection = selection;
    self._onLocationChange = onLocationChange;

    self._selection
      .querySelector("#location-button")
      .addEventListener("click", () => self._onLocationChange());
  }

  getLocation() {
    const self = this;
    return self._selection.querySelector("#location-input").value;
  }
}

class ShapefileFormPresenter {
  constructor(selection, onChange) {
    const self = this;
    self._selection = selection;
    self._onChange = onChange;

    self._selection.addEventListener("change", () => {
      self._onChange();
    });
  }

  getFiles() {
    const self = this;
    return self._selection.files;
  }

  disable() {
    const self = this;
    self._selection.disabled = true;
  }

  getIsDisabled() {
    const self = this;
    return self._selection.disabled;
  }
}

class MapLinkPresenter {
  constructor(selection, typeName) {
    const self = this;
    self._selection = selection;
    self._typeName = typeName;
  }

  updateUrl(tileserverEndpoint, affiliation, fireEventName) {
    const self = this;
    const newUrl = self._getUrl(tileserverEndpoint, affiliation, fireEventName);
    self._setHref(newUrl);
  }

  _getUrl(tileserverEndpoint, affiliation, fireEventName) {
    const self = this;
    const typeName = self._typeName;
    return `${tileserverEndpoint}/map/${affiliation}/${fireEventName}/${typeName}`;
  }

  _setHref(newHref) {
    const self = this;
    self._selection.href = newHref;
  }
}

class ProductsListPresenter {
  constructor(selection) {
    const self = this;
    self._selection = selection;
  }

  insertProducts(products) {
    const self = this;
    const list = document.createElement("ul");

    const items = products.map((x) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      const text = document.createTextNode(product.getProductType());

      link.href = products.getProductUrl();
      link.appendChild(text);
      item.appendChild(link);

      return item;
    });

    items.forEach((item) => list.appendChild(item));

    self._selection.append(list);
  }
}

class FireAnalysisMetaFormPresenter {
  constructor(selection, onSubmit) {
    const self = this;
    self._selection = selection;
    self._onSubmit = onSubmit;

    self._selection.addEventListener("submit", (e) => {
      e.preventDefault();
      self._onSubmit();
    });
  }

  getFireEventName() {
    const self = this;
    return selection.querySelector("#fire_event_name").value;
  }

  getAffiliation() {
    const self = this;
    return selection.querySelector("#affiliation").value;
  }

  getFormContents() {
    const self = this;

    const getVal = (targetId) =>
      self._selection.querySelector("#" + targetId).value;

    const prefireStart = new Date(getVal("prefire-start"));
    const prefireEnd = new Date(getVal("prefire-end"));
    const postfireStart = new Date(getVal("postfire-start"));
    const postfireEnd = new Date(getVal("postfire-end"));
    const fireEventName = getVal("fire_event_name");
    const affiliation = getVal("affiliation");

    return new FireAnalysisMetaFormContents(
      prefireStart,
      prefireEnd,
      postfireStart,
      postfireEnd,
      fireEventName,
      affiliation
    );
  }
}

class IndicatorAreaPresenter {
  constructor(selection) {
    const self = this;
    self._selection = selection;
    self._uploadStatus = AnalysisStatus.PENDING;
    self._rangelandStatus = AnalysisStatus.PENDING;
    self._ecolassStatus = AnalysisStatus.PENDING;
    self._burnAnalysisStatus = AnalysisStatus.PENDING;
  }

  showAllLoading() {
    const self = this;
    self._show("upload-loading");
    self._show("burn-analysis-loading");
    self._show("ecoclass-analysis-loading");
    self._show("rap-analysis-loading");
    self._show("products-loading");
  }

  showFireNotFound() {
    const self = this;
    alert(
      "No fire boundary detected within the AOI. Please try again by refreshing the page."
    );
    self._hide("burn-analysis-loading");
    self._hide("burn-analysis-success");
    self._hide("upload-loading");
    self._hide("upload-success");
    self._hide("ecoclass-analysis-loading");
    self._hide("ecoclass-analysis-success");
    self._hide("rap-analysis-loading");
    self._hide("rap-analysis-success");
    self._hide("products-loading");
  }

  showSatellitePassInfo(burnAnalysisResponse) {
    const satellitePassInfo = burnAnalysisResponse.getSatellitePassInfo();

    document.querySelector("#n-prefire-items").innerHTML =
      "<i>Number of prefire images: </i>" +
      satellitePassInfo.n_prefire_passes.toString();
    document.querySelector("#n-postfire-items").innerHTML =
      "<i>Number of postfire images: </i>" +
      satellitePassInfo.n_postfire_passes.toString();
    document.querySelector("#latest-pass").innerHTML =
      "<i>Latest pass obtained: </i>" + satellitePassInfo.latest_pass;
  }

  showSkippedAnalyses() {
    debugger;
    if (this._uploadStatus == AnalysisStatus.PENDING) {
      this._hide("upload-loading");
      this._show("upload-skipped");
    }
    if (this._burnAnalysisStatus == AnalysisStatus.PENDING) {
      this._hide("burn-analysis-loading");
      this._show("burn-analysis-skipped");
    }
    if (this._ecolassStatus == AnalysisStatus.PENDING) {
      this._hide("ecoclass-analysis-loading");
      this._show("ecoclass-analysis-skipped");
    }
    if (this._rangelandStatus == AnalysisStatus.PENDING) {
      this._hide("rap-analysis-loading");
      this._show("rap-analysis-skipped");
    }
  }

  _show(targetId) {
    const self = this;
    document.getElementById(targetId).style.display = "block";
  }

  _hide(targetId) {
    const self = this;
    document.getElementById(targetId).style.display = "none";
  }

  // Upload

  showUploadSuccess() {
    const self = this;
    self._hide("upload-loading");
    self._show("upload-success");
    self._uploadStatus = AnalysisStatus.SUCCESS;
  }

  showUploadFail() {
    const self = this;
    self._hide("upload-loading");
    self._show("upload-failure");
    self._uploadStatus = AnalysisStatus.FAILURE;
    self.showSkippedAnalyses();
    alert("Upload failed");
  }

  // Burn Analysis

  showBurnAnalysisSuccess(burnAnalysisResponse) {
    const self = this;
    this.showSatellitePassInfo(burnAnalysisResponse);
    self._hide("burn-analysis-loading");
    self._show("burn-analysis-success");
    self._burnAnalysisStatus = AnalysisStatus.SUCCESS;
  }

  showBurnAnalysisFailed() {
    const self = this;
    self._hide("burn-analysis-loading");
    self._show("burn-analysis-failure");
    self._burnAnalysisStatus = AnalysisStatus.FAILURE;
    self.showSkippedAnalyses();
    alert("Burn analysis failed");
  }

  showBurnAnalysisSkipped() {
    const self = this;
    self._hide("burn-analysis-loading");
    self._show("burn-analysis-skipped");
  }

  // Seed Point submission (in the place of burn analysis)

  showSeedPointSubmissionWaiting() {
    const self = this;
    self._hide("burn-analysis-loading");
    self._show("seed-point-submission");
  }

  showSeedPointSubmissionPending() {
    const self = this;
    self._hide("seed-point-submission");
    self._show("burn-analysis-pending");
  }

  waitForSeedPointSubmission() {
    const self = this;
    const seedSubmissionButton = document.querySelector(
      "#seed-point-submission"
    );

    // Return a Promise that resolves when the button is clicked
    return new Promise((resolve) => {
      seedSubmissionButton.addEventListener(
        "click",
        () => {
          debugger;
          resolve();
        },
        { once: true }
      );
    });
  }

  // EcoClass

  showEcoclassSuccess() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._show("ecoclass-analysis-success");
    self._ecolassStatus = AnalysisStatus.SUCCESS;
  }

  showEcoclassFailed() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._show("ecoclass-analysis-failure");
    self._ecolassStatus = AnalysisStatus.FAILURE;
    self.showSkippedAnalyses();
    alert("Ecoclass analysis failed");
  }

  showEcoclassSkipped() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._show("ecoclass-analysis-skipped");
  }

  // Rangeland

  showRangelandSuccess() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-success");
    self._rangelandStatus = AnalysisStatus.SUCCESS;
  }

  showRangelandFailed() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-failure");
    self._rangelandStatus = AnalysisStatus.FAILURE;
    self.showSkippedAnalyses();
    alert("Rangeland Analysis Platform query failed");
  }

  showRangelandSkipped() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-skipped");
  }
}
