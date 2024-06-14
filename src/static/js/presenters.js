class MapPresenter {
  constructor(targetId, onAoiDrawn) {
    const self = this;

    const map = L.map(targetId).setView([39.7749, -100.4194], 5);

    // Create panes to properly order basemaps and boundaries
    map.createPane("basemaps");
    map.getPane("basemaps").style.zIndex = 2;

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
    const editableLayers = new L.FeatureGroup();
    map.addLayer(editableLayers);

    // Initialize the draw control and pass it the FeatureGroup of editable layers
    const drawControl = new L.Control.Draw({
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

      onAoiDrawn();
    });

    self._innerMap = map;
    self._editableLayers = editableLayers;
    self._drawControl = drawControl;
    self._aoiControl = null;
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

  removeDrawControl() {
    const self = this;
    self._innerMap.removeControl(self._drawControl);
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
  showAllLoading() {
    const self = this;
    self._show("upload-loading");
    self._show("burn-analysis-loading");
    self._show("ecoclass-analysis-loading");
    self._show("rap-analysis-loading");
    self._show("products-loading");
  }

  showUploadSuccess() {
    const self = this;
    self._hide("upload-loading");
    self._show("upload-success");
  }

  showUploadFail() {
    const self = this;
    self._hide("upload-loading");
    self._show("upload-failure");
    alert("Upload failed");
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

  showSatelliePassInfo(burnAnalysisResponse) {
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

  showBurnAnalysisFailed() {
    const self = this;
    self._hide("burn-analysis-loading");
    alert("Burn analysis failed");
  }

  showBurnAnalysisSuccess(burnAnalysisResponse) {
    const self = this;
    this.showSatelliePassInfo(burnAnalysisResponse);
    self._hide("burn-analysis-loading");
    self._show("burn-analysis-success");
  }

  showBurnAnalysisSkipped() {
    const self = this;
    self._hide("burn-analysis-loading");
    self._show("burn-analysis-skipped");
  }

  showEcoclassSuccess() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._hide("ecoclass-analysis-success");
  }

  showEcoclassFailed() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._show("ecoclass-analysis-failure");
    alert("Ecoclass analysis failed");
  }

  showEcoclassSkipped() {
    const self = this;
    self._hide("ecoclass-analysis-loading");
    self._show("ecoclass-analysis-skipped");
  }

  showRangelandSuccess() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-success");
  }

  showRangelandFailed() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-failure");
    alert("Rangeland Analysis Platform query failed");
  }

  showRangelandSkipped() {
    const self = this;
    self._hide("rap-analysis-loading");
    self._show("rap-analysis-skipped");
  }

  _show(targetId) {
    const self = this;
    document.getElementById(targetId).style.display = "block";
  }

  _hide(targetId) {
    const self = this;
    document.getElementById(targetId).style.display = "none";
  }
}
