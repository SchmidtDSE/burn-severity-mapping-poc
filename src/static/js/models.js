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
  constructor(executed, fireFound, derivedBoundary, satellitePassInfo) {
    const self = this;
    self._executed = executed;
    self._fireFound = fireFound;
    self._derivedBoundary = derivedBoundary;
    self._satellitePassInfo = satellitePassInfo;
  }

  getExecuted() {
    const self = this;
    return self._executed;
  }

  getFireFound() {
    const self = this;
    return self._fireFound;
  }

  getDerivedBoundary() {
    const self = this;
    return self._derivedBoundary;
  }

  getSatellitePassInfo() {
    const self = this;
    return self._satellitePassInfo;
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

    const formData = new URLSearchParams();
    formData.append("file", shapefile);
    formData.append("fire_event_name", metadata.getFireEventName());
    formData.append("affiliation", metadata.getAffiliation());
    formData.append("shapefule", shapefile);
    formData.append("derive_boundary", false);

    const request = { method: "POST", body: formData };
    return fetch(`/api/upload/shapefile-zip`, request).then(get200Json);
  }

  analyzeBurn(metadata, geojson, useDrawnShape) {
    const self = this;

    const performFetch = () => {
      const body = JSON.stringify({
        geojson: geojson,
        fire_event_name: metadata.getFireEventName(),
        affiliation: metadata.getAffiliation(),
        derive_boundary: useDrawnShape,
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
                true,
                responseJson.derived_boundary,
                responseJson.satellite_pass_information
              )
          );
      } else if (statusCode == 204) {
        return new BurnAnalysisResponse(true, false, null, null);
      } else {
        return new BurnAnalysisResponse(false, false, null, null);
      }
    };

    return performFetch().then(interpretResponse);
  }

  // TODO: getEcoclass, getRangelandAnalysis
}
