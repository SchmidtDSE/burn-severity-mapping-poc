### Goals

Near-term
- Enable NPS land managers to rapidly understand the severity of fires in arid landscapes, using rapidly-updated `Sentinel-2` and/or `LANDSAT` imagery, using a DSE-developed modelling approach and web application collaboratively designed with NPS end-users

Long-term
- Develop and refine the tool to support NPS efforts in post-fire recovery, by investigating the post-fire effects of firebreak strategies, effectiveness of re-vegetation efforts, community range migration, among others

### Current Approach: BAER / BARC Classifications

BAER is generated rapidly after a fire occurs, but is not a great representation of 'true' vegetation loss for a few reasons (motivated in part by *Safford et. al. 2008*). 

1) **BARC framework and validation are not designed around arid ecosystems, and thus lack sensitivity to low biomass - comparisons of pre and post-fire comparisons are absolute, not relative**
2) BARC is not very useful at low spatial resolutions, due to the BAER minimum delineations being around 40 acres
3) BARC severity classifications vary from fire to fire, and classification thresholds are determined manually using opaque methodology, making spatial and temporal comparisons across fires difficult
4) BARC is not validated with quantitative field data, so while relative comparisons might be valid, it is hard to make accurate **absolute** estimations of vegetation loss post-fire.

### Best Practice: Relative Spectral Metrics

To account for the fact that JOTR and other arid parks exist have relatively little biomass in vegetation compared to forest counterparts considered by BARC, we plan to analyze a suite of relative spectral metrics that adjust the fire severity metric of interest (usually the difference in spectral metrics before and after a fire).

### Step 1 - Develop Data / Modelling Infrastructure

Inputs:
- High frequency, low spatial resolution, highest spectral resolution remote sensing data
	- `Sentinel-2`, `LANDSAT`
- Low frequency, higher spatial resolution, low spectral resolution 
	- National Agricultural Imagery Program (`NAIP`)
- One-off frequency, extremely high spatial resolution, variable spectral resolution
	- LIDAR imagery from previous survey work

In the context of fire severity modelling, absolute metrics, such as the *Normalized Burn Ratio* ($NBR$), tend to be more effective for comparison across high and low biomass areas, but tend to be biased low in low biomass areas since the absolute changes ($dNBR$) are small in magnitude according to lack of adjustment. 

$$ NBR = \frac{NIR - SWIR}{NIR + SWIR} $$

$$ dNBR = NBR_{prefire} - NBR_{postfire}$$

To address these issues, some commonly accepted adjustments include the *Relative Difference in Normalized Burn Ratio* ($RdNBR$), as well as the *Relativized Burn Ratio* ($RBR$),  both of which attempt to adjust the relative change by the reflectance of the area pre-fire, such that fire severity is scaled to local reflectance in each given pixel.

$$RdNBR = \frac{dNBR}{|(NBR_{prefire})^{0.5}|}$$

$$ RBR = \frac{dNBR}{NBR_{prefire} +1.001}$$

Each of these metrics can be derived from satellite imagery, at various degrees of temporal and spatial resolution. The simplest approach would be to settle on one source (likely `Sentinel-2`, as it has the higher temporal resolution than `LANDSAT`), and interpolate values between collection. However, a particular challenge identified in the case of immediate post-fire analysis is the potential occlusion of smoke - most approaches employ some manual approaches to find the best available pre-fire and post-fire images, which could lead to (1) some vegetative cover/biomass bias due phenology between image dates or (2) lag in analysis time in waiting for smoke-free imagery to be collected, since satellites return at best every 5 days. 

If we discover that relying on a imaging source is insufficient, either due to a lack of timeliness in imaging after fire (due to smoke or cloud occlusion) or simply due to issues with ground-truth accuracy (described in step 2), we may investigate a method which incorporates multiple imagery sources, as illustrated with `ESTARFM` fusion model employed in *Liu et. al. 2022*. 
### Step 2 - Validate Using NPS, BLM, USGS Ground-Truth

Inputs:
- Remote Sensing data as discussed above
- Vegetation cover data
	- Assessment, Inventory and Monitoring data from BLM / USGS, used to train [USDA's Rangeland Analysis Platform](https://rangelands.app/)
	- Any and All NPS data that resemble AIM format (*specific fields and aggregations to be discussed with the JOTR/NPS team and through further investigation*)
- Exogenous Land Features
	- Soil / Lithography inputs using SSURGO, WebSoilSurvey, etc
	- Terrain information using Digital Elevation Models (DEM) or other finer sources

Using the approach described above, we will perform an initial analysis describing how well each relative metric (using *just* a remote sensing approach) approximates vegetation metrics derived through ground truth data. An example of this approach, which focuses instead on the *Composite Burn Index* (CBI), is illustrated in *Cardil et. al. 2019*.

Depending on the results here, we may discover that one of the metrics above is a good enough approximation of reality to prove useful to the NPS in fire recovery efforts, and thus would move on to step 3. 

However, if we are not satisfied with the accuracy of such a model, another approach to this step would be to use vegetation cover as a target variable in a supervised learning model. Instead of treating the spectral indices as the output themselves, we might use these spectral indices as inputs (potentially including exogenous land features) to directly predict vegetation cover percentage. Such an approach would require more complete and land-cover-balanced vegetation data, but might result in better performance on NPS-managed lands in Southern California. 

### Step 3 – Develop Web Application and Interactive Elements

Alongside modelling efforts, following guidance and feedback from JOTR staff and NPS stakeholders, we plan to develop an interactive web application which allows managers to visualize, for example:
- (1) Point-in-time estimates of vegetative cover
- (2) Trends in green-up and senescence
- (3) Vegetative effects of disturbance

The metrics visualized within this tool will be highly dependent on evidence of utility to park managers, from steps 1 and 2, and are subject to change throughout the design process and/or after project 'completion'.

### References
Cardil, A., Mola-Yudego, B., Blázquez-Casado, Á. & González-Olabarria, J. R. Fire and burn severity assessment: Calibration of Relative Differenced Normalized Burn Ratio (RdNBR) with field data. _Journal of Environmental Management_ **235**, 342–349 (2019).

Parks, S., Dillon, G. & Miller, C. A New Metric for Quantifying Burn Severity: The Relativized Burn Ratio. _Remote Sensing_ **6**, 1827–1844 (2014).

Safford, H. D., Miller, J., Schmidt, D., Roath, B. & Parsons, A. BAER Soil Burn Severity Maps Do Not Measure Fire Effects to Vegetation: A Comment on Odion and Hanson (2006). _Ecosystems_ **11**, 1–11 (2008).

Liu, Z. _et al._ Research on Vegetation Cover Changes in Arid and Semi-Arid Region Based on a Spatio-Temporal Fusion Model. _Forests_ **13**, 2066 (2022).
