class Product {
  constructor(productType, productUrl) {
    const self = this;
    self._productType = productType;
    self._productUrl = productUrl;
  }

  getProductType() {
    const self = this;
    return self._productType;
  }

  getProductUrl() {
    const self = this;
    return self._productUrl;
  }
}

class BurnAnalysisResponse {
  constructor(executed, satellitePassInfo, cloudCogPaths) {
    const self = this;
    self._executed = executed;
    self._satellitePassInfo = satellitePassInfo;
    self._cloudCogPaths = cloudCogPaths;
  }

  getExecuted() {
    const self = this;
    return self._executed;
  }

  getSatellitePassInfo() {
    const self = this;
    return self._satellitePassInfo;
  }

  getCloudCogPaths() {
    const self = this;
    return self._cloudCogPaths;
  }
}

class FireAnalysisMetaFormContents {
  constructor(
    prefireStart,
    prefireEnd,
    postfireStart,
    postfireEnd,
    fireEventName,
    affiliation
  ) {
    const self = this;
    self._prefireStart = prefireStart;
    self._prefireEnd = prefireEnd;
    self._postfireStart = postfireStart;
    self._postfireEnd = postfireEnd;
    self._fireEventName = fireEventName;
    self._affiliation = affiliation;
  }

  getPrefireStart() {
    const self = this;
    return self._prefireStart;
  }

  getPrefireEnd() {
    const self = this;
    return self._prefireEnd;
  }

  getPostfireStart() {
    const self = this;
    return self._postfireStart;
  }

  getPostfireEnd() {
    const self = this;
    return self._postfireEnd;
  }

  getFireEventName() {
    const self = this;
    return self._fireEventName;
  }

  getAffiliation() {
    const self = this;
    return self._affiliation;
  }

  getProblems() {
    const self = this;

    const checkDatesGiven = () => {
      const dates = [
        self._prefireStart,
        self._prefireEnd,
        self._postfireStart,
        self._postfireEnd,
      ];
      const nanDates = dates.filter((x) => isNaN(x));
      if (nanDates.length > 0) {
        return "Please enter valid dates";
      } else {
        return null;
      }
    };

    const checkDatesSequential = () => {
      const checks = [
        self._prefireStart >= self._prefireEnd,
        self._prefireEnd >= self._postfireStart,
        self._postfireStart >= self._postfireEnd,
      ];
      const invalidChecks = checks.filter((x) => x == true);
      if (invalidChecks.length > 0) {
        return "Please enter valid date ranges";
      } else {
        return null;
      }
    };

    const checkFireEventName = () => {
      if (self._fireEventName === "") {
        return "Please enter a fire event name";
      } else {
        return null;
      }
    };

    const possibleProblems = [
      checkDatesGiven(),
      checkDatesSequential(),
      checkFireEventName(),
    ];

    const foundProblems = possibleProblems.filter((x) => x !== null);

    return foundProblems;
  }
}

class FloodFillSegmentationResponse {
  constructor(executed, fireEventName, affiliation, derivedBoundary) {
    const self = this;
    self._executed = executed;
    self._fireEventName = fireEventName;
    self._affiliation = affiliation;
    self._derivedBoundary = derivedBoundary;
  }

  getExecuted() {
    const self = this;
    return self._executed;
  }

  getFireEventName() {
    const self = this;
    return self._fireEventName;
  }

  getAffiliation() {
    const self = this;
    return self._affiliation;
  }

  getDerivedBoundary() {
    const self = this;
    return self._derivedBoundary;
  }
}

class ApiFacade {
  getDerivedProducts(fireEventName, affiliation) {
    const self = this;

    const body = JSON.stringify({
      fire_event_name: fireEventName,
      affiliation: affiliation,
    });

    const request = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body,
    };

    return fetch("/api/list/derived-products", request)
      .then(get200Json)
      .then((response) => {
        return Object.entries(response).map((entry) => {
          const productType = entry[0];
          const productUrl = entry[1];
          return new Product(productType, productUrl);
        });
      });
  }

  uploadDrawnShape(metadata, drawnGeojsonStr) {
    const self = this;

    const formData = new URLSearchParams();
    // formData.append("file", $("#shp_zip")[0].files[0]); TODO: Not needed here?
    formData.append("fire_event_name", metadata.getFireEventName());
    formData.append("affiliation", metadata.getAffiliation());

    console.log(drawnGeojsonStr);
    formData.append("geojson", drawnGeojsonStr);

    const request = { method: "POST", body: formData };
    return fetch(`/api/upload/drawn-aoi`, request).then(get200Json);
  }

  uploadShapefile(metadata, shapefile) {
    const self = this;

    const formData = new FormData();
    formData.append("file", shapefile);
    formData.append("fire_event_name", metadata.getFireEventName());
    formData.append("affiliation", metadata.getAffiliation());
    formData.append("derive_boundary", false);

    const request = { method: "POST", body: formData };
    return fetch(`/api/upload/shapefile-zip`, request).then(get200Json);
  }

  analyzeBurn(metadata, geojson) {
    const self = this;

    const performFetch = () => {
      const body = JSON.stringify({
        geojson: geojson,
        fire_event_name: metadata.getFireEventName(),
        affiliation: metadata.getAffiliation(),
        date_ranges: {
          prefire: [metadata.getPrefireStart(), metadata.getPrefireEnd()],
          postfire: [metadata.getPostfireStart(), metadata.getPostfireEnd()],
        },
      });

      const request = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
      };

      return fetch("/api/analyze/spectral-burn-metrics", request);
    };

    const interpretResponse = (response) => {
      const statusCode = response.status;
      if (statusCode == 200) {
        return response
          .json()
          .then(
            (responseJson) =>
              new BurnAnalysisResponse(
                true,
                responseJson.satellite_pass_information,
                responseJson.cloud_cog_paths
              )
          );
      } else if (statusCode == 204) {
        return new BurnAnalysisResponse(true, null, null);
      } else {
        return new BurnAnalysisResponse(false, null, null);
      }
    };

    return performFetch().then(interpretResponse);
  }

  refineFloodFill(metadata, geojson) {
    const self = this;

    const performFetch = () => {
      const body = JSON.stringify({
        geojson: geojson,
        fire_event_name: metadata.getFireEventName(),
        affiliation: metadata.getAffiliation(),
      });

      const request = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
      };

      return fetch("/api/refine/flood-fill-segmentation", request);
    };

    const interpretResponse = (response) => {
      const statusCode = response.status;
      if (statusCode == 200) {
        return response.json().then(
          (responseJson) =>
            new FloodFillSegmentationResponse(
              true,
              true, // Fire was detected
              responseJson.fire_event_name,
              responseJson.affiliation,
              responseJson.derived_boundary
            )
        );
      } else if (statusCode == 204) {
        // Analysis succeeded but no fire was detected
        return new FloodFillSegmentationResponse(true, false, null, null, null);
      } else {
        // Analysis failed
        return new FloodFillSegmentationResponse(
          false,
          false,
          null,
          null,
          null
        );
      }
    };

    return performFetch().then(interpretResponse);
  }
}
