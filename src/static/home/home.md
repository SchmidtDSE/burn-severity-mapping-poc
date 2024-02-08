## Wildfire Severity and Recovery Tool, Version 0

**Note: This tool and website are under ongoing development - it is recommended that you save any and all analytical outputs you deem essential.**

<div class="center-flexbox">
    <a href="/upload">
        <img src="static/home/upload.png" alt="Upload" class="nav-icon" />
        <p>Upload</p>
    </a>
    <a href="/directory">
        <img src="static/home/directory.png" alt="Directory" class="nav-icon"/>
        <p>Directory</p>
    </a>
    <a href="/map/DSE/York/rbr">
        <img src="static/home/map.png" alt="Example Map" class="nav-icon"/>
        <p>Example Map</p>
    </a>
</div>

### How To

Begin by visiting the [Upload](/upload) page - here you will be able to enter:

- An area of interest, either:
  - A shapefile (containing `.shp`, `.shx`, `.prj` and opitonally, `.dbf`) defining a fire boundary
  - A rough area of interest, where we attempt to derive the fire boundary using the `RBR` metric defined below
- Pre-fire and post-fire date ranges (approximately 1-3 weeks before ignition date, and 1-3 weeks after suppression)
- Fire event name
- Affiliation (for file organization / naming purposes)

After submission, the tool will:

1. Upload the burn boundary (or derive it using your defined AOI)
2. Collect satellite imagery for your selected dates within the burn boundary, producing fire severity metrics
3. Attempt to fetch [Ecological Dynamics Interpretive Tool](https://edit.jornada.nmsu.edu/) dominant cover information
4. Attempt to fetch [Rangeland Analysis Platform](https://rangelands.app/rap/) biomass data

If all four of these processes succeed, you will be presented download links for all of the analytical products generated, including an interactive map visualizing the results. If, at any time, you'd like to access these again, you can simply visit the [Directory](/directory), where you can select your affiliation and fire event name once more to access these files again.

#### Developer Notes

As this is a work in progress, there are a few things to note regarding usage of the tool:

- Pages take a few seconds to load upon changing pages - this is expected
- Especially on first map view, the burn metrics may take several seconds to render properly. This can typically be resolved by refreshing the page, or switching between the `Continious` and `Categorical` burn severity layer, which will trigger a re-render.
- The combinaton of `Fire Event Name` and `Affiliation` _must be unique_. If you re-submit a request using the same `Fire Event Name` and `Affiliation`, you will overwrite the existing products within the server. Please feel free to do so if you've made a mistake or if you are experimenting!
- Within the map view, the left side legend may be obscured on some screens - this may occur if your burn area is sufficently rich with cover type information and is a known issue. You may be able to resolve this by zooming out within your browser.

## Background

This is a very early development prototype of a _Wildfire Severity and Recovery Tool_, devloped by Eric and Wendy Schmidt Center for Data Science & Environment (DSE) at Berkeley in Collaboration with the National Parks Service, meant to gather feedback from interested collaborators and users.

The core of this collaboration comes from a need to better understand the severity of fires occuring in low biomass areas - in our initial case, in Southern California (specifically, Joshua Tree National Park and Mojave National Preserve).

This tool uses publicly available satellite imagery (currently, the European Space Agency's _Sentinel 2_ imagery) to estimate fire severity metrics on-demand.

#### Methodology

The process of deriving burn severity metrics from satellite imagery typically involves comparing imagery from before and after a fire event, to determine how 'different' these images are in terms of reflective vegetation. Specifically, these metrics exploit the difference in two spectral bands provided by satellite imagery:

- **Near Infrared**, which is highly reflective in healthy vegetation
- **Shortwave Infrared**, which is highly reflective in burned areas

![Exploting Spectral Response Curves](static/home/nir_swir.jpg)

##### Absolute Metrics

Absolute metrics, such as the _Normalized Burn Ratio_ ($NBR$), tend to be more effective for comparison across high and low biomass areas, since they essentially describe the _absolute difference_ in reflectiveness of healthy vegetation, regardless of how much vegetation existed there in the first place.

$$ NBR = \frac{NIR - SWIR}{NIR + SWIR} $$

$$ dNBR = NBR\_{prefire} - NBR\_{postfire} $$

In theory, this means that higher differences represent larger magnitudes of lost healthy vegetation. However, these tend to be biased low in low biomass areas or areas with sparse vegetation, because the absolute loss of vegetation, even in what would be considered an extreme fire event, is lower than the possible loss of vegetation in a higher biomass area.

##### Relative Metrics

Relative metrics, in contrast, scale the estimate of fire intensity at any particular point to its own prefire conditions - essentially, the intensity of a fire is expressed as a percentage of how much healthy vegetative signal was lost.

$$RdNBR = \frac{dNBR}{|(NBR_{prefire})^{0.5}|}$$

$$ RBR = \frac{dNBR}{NBR\_{prefire} +1.001}$$

This means that, between low and high biomass areas, you would observe equivalent $RBR$ values even if the high biomass area experienced higher $dNBR$ values than the low biomass area.

### References

Cardil, A., Mola-Yudego, B., Blázquez-Casado, Á. & González-Olabarria, J. R. Fire and burn severity assessment: Calibration of Relative Differenced Normalized Burn Ratio (RdNBR) with field data. _Journal of Environmental Management_ **235**, 342–349 (2019).

Parks, S., Dillon, G. & Miller, C. A New Metric for Quantifying Burn Severity: The Relativized Burn Ratio. _Remote Sensing_ **6**, 1827–1844 (2014).

Safford, H. D., Miller, J., Schmidt, D., Roath, B. & Parsons, A. BAER Soil Burn Severity Maps Do Not Measure Fire Effects to Vegetation: A Comment on Odion and Hanson (2006). _Ecosystems_ **11**, 1–11 (2008).

Liu, Z. _et al._ Research on Vegetation Cover Changes in Arid and Semi-Arid Region Based on a Spatio-Temporal Fusion Model. _Forests_ **13**, 2066 (2022).
