## 1.SATELLITE BANDS.

- It is simply a specific range of wavelenghts of light.
- There are 13 bands in this satellite.
- There are also two types of resolutions to remember:
1. Spatial resolution - how big each pixel is on the ground(10, 20 or 60m)
2. Wavelength - the specific color/type of light the band captures.
   
**1. Group 1: The visible & Coastal Bands**

-These are mostly used to create 'True Color' images, what we would see if we were floating in space.

1. Band 1 - Coastal Aerosol(60m)
- Is mostly used for atmospheric correction (removing haze) and monitoring shallow coastal waters.

2. Band 2 - Blue(10m)
- Used to map shallow waters, distinguishing soil from vegetation and creatinf true color images.
  
3. Band 3 - Green(10m)
- Measures the peak of vegetation health and creates true-color images.

4. Band 4 - Red(10m)
- Used for chlorophyll absorption. healthy plants absorb red light so this band is crucial for calculating vegetation health.


**2. Group 2: The 'Red Edge' bands(The Secret to Plant Health)**

- This is unique to Sentinel-2, between the red and the infra-rd there is a sharp jump in how much light plants reflect, these bands capture that exact transition:

5. Band 5 -Vegetation Red edge(20m)
6. Band 6 - Vegetation red edge(20m)
7. Band 7 - same as the other 2 bands.

- These are highly sensitive to plant stress, cholorphyl content and nitrogen levels.
- If a crop is starting to get sick, these bands will show it.

8. Band 8 - Near-Infared(NIR) (10m)
- This is the most important band for vegetation. Healthy plants reflect amassive amount of NIR light.
- On looking at a false-color image where NIR is mapped to red, healthy forests glow birght red.


**3. Group 3: The Water Vapor & Cirrus Bands(ATmospheric Correction)**

-These bands are mostly used by scientist to 'clean up ' the image rather than for looking at the ground.

9. Band 8A - Narrow Near-Infared(20m), similar to band 8 but narrower. Used for more precise vegetation analysis.

10. Band 9 - Water vapor (60m) - Used to detect water vapor in the atmosphere and is used to correct the image so that we can accurately measure the ground.

11. Band 10 - Shortwave Infarred / Cirrus (60m)
- It detects thin, high-altitude clouds that might be invisible in true-color images. It is used to mask these clouds out.

**4. Group 4: The Shortwave Infrared (SWIR) bands (Geology & Moisture)**

-These bands are great for things that are not plants, rocs, soil moisture and plant water stress.

12. Band 11 - SWIR 1(20m).
- It is excellent for distinguishing between snow, clouds and ice.
- Also very sensitive to soil moisture and plant water stress.

13. Band 12 - SWIR 2(20m)
- Is used in geology to identify different types of rocks and minerals, mapping wildfires and detecting oil spills.


### How These Bands Are Used

-The magic of Sentinel-2 comes from combining bands mathematically to create 'Indices', here's how it is practically done:

1. True color : Red(B4) + Green(B3) + Blue(B2)
- This results in a natural looking photo of the earth.

2. NDVI (Normalized Difference Vegetation Index):  (Band 8 - Band 4) / (Band 8 + Band 4)
- Is used to measure plant health.
- Healthy plants reflect a lot of NIR (B8) and absord a lot of red(B4)
- The values range from -1 to +1.
- Water/clouds are negative.
- Bare soil is around 0.1 - 0.2
- Healthy, lush forests are 0.7-0.9

3. NDWI (Normalized Difference Water Index)
- Is used tomap water bodies and floods.