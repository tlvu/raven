Changes
=======

0.11.x
------
* Update to Raven 3.0
* Update to xclim 0.18
* Update to xarray 0.16


0.10.x (2020-03-09) Oxford
--------------------------
* `suppress_ouput` also triggers `:DontWriteWatershedStorage`
* Added support for ERA5 (hourly), NRCan and CANOPEX datasets
* Support linear transforms (unit changes)
* Calibration now uses :SuppressOutput by default
* Added options for rain_snow_fraction, evaporation and ow_evaporation
* Updated Raven version to 295
* Support passing shapes as zip files


0.9.x (2019-11-11)
------------------
* Return configuration files used to run model in a zip archive


0.8.x (2019-10-22)
------------------
* Added more documentation for users
* Fixed reprojection errors in GIS utilities
* Specified HydroBASINS in lieu of HydroSHEDS in processes
* Optimized memory usage in ReadTheDocs builds when using Sphinx autodoc by employing mock
* Cleaner GeoJSON outputs for many subsetting processes
* Employed ipyleaflets for notebook-based web-maps
* Run py.test on notebooks from local or remote server


0.7.x (2019-06-25)
------------------

* Regionalization database
* Graphics for frequency analysis
* Many new notebook tutorials
* Bug fixes


0.6.x (2019-06-05)
------------------

* Regionalization process allowing the estimation of parameters of ungauged watersheds
* Added time series analysis processes, including frequential analysis
* Added processes creating graphics
* GIS processes now use GeoServer capabilities
* Docker configuration


0.5.0 (2019-04-12)
------------------

* Added watershed geospatial analysis processes
  - Hydroshed basin selection (with upstream contributors)
  - Watershed properties
  - DEM property analysis
  - Land-use property analysis
* Added multi-parameter parallel simulations
* Added multi-model parallel simulations
* Added multi-bassin parallel simulations


0.4.0 (2019-03-12)
------------------

* Added model calibration processes using Ostrich
* Added support for launching a singularity image
* Added library functions for model regionalization


0.3.0 (2019-01-24)
------------------

* Adds process for MOHYSE emulator
* Adds process for HBV-EC emulator


0.2.0 (2018-11-29) Washington
-----------------------------

* Provides generic RAVEN framework configuration
* Process for GR4J-Cemaneige emulator
* Process for HMETS emulator


