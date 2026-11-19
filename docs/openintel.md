# OpenIntel

Open the tab, choose a region and select a map point or report. On a new installation the bundled sample set opens even without a connection. Start live updates to fetch observations for the visible layers. Camera streams require a connection. Pausing the updates keeps the last reports available locally.

| Layer | Available coverage and access |
| --- | --- |
| Aircraft | [adsb.lol](https://www.adsb.lol/docs/open-data/api) receiver reports within 100 nautical miles of the regional centre. Coverage depends on receivers. |
| Vessels | [Fintraffic](https://www.digitraffic.fi/en/marine-traffic/) positions in Finland. [AISStream](https://aisstream.io/documentation) offers wider coverage with your own session key. Its live observations expire from memory. |
| Cameras | Timestamped [Fintraffic](https://www.digitraffic.fi/en/road-traffic/) camera stills in Finland. Open the catalogue for the [Maui beach player](https://www.mauirealestate.net/live/), [Traffic Scotland](https://www.traffic.gov.scot/traffic-information/traffic-cameras) and [Explore](https://explore.org/livecams) viewers. |
| Satellites | Selected [CelesTrak](https://celestrak.org/NORAD/documentation/gp-data-formats.php) station orbits. SGP4 calculates positions and approximate geometric passes offline for the selected observer. Elements expire after fourteen days. Daylight, terrain and weather affect visibility. |
| Earth imagery | Acquire a dated [NASA Terra MODIS composite](https://www.earthdata.nasa.gov/data/tools/worldview) for the selected region. Save the image to retain it offline. Select a second available date in the detail panel to compare. |
| Hazards and sea | Weekly [USGS earthquake reports](https://earthquake.usgs.gov/earthquakes/feed/v1.0/index.php) and the latest [NOAA buoy readings](https://www.ndbc.noaa.gov/) from reporting stations. |
| Receiver | Import a GeoJSON FeatureCollection of Point features with title and ISO UTC time properties. Select the region containing the points. A decoder must supply these files. |

Latest shows one report per object. The time slider reconstructs observations by their reported time, and the selected trail connects nearby reports. Publisher coverage, delays and regional limits can leave the map empty. The catalogue shows the last fetch result. Aircraft refresh at most every five minutes per region, Finnish AIS every two minutes, buoy readings every ten minutes and orbital elements every two hours. Live updates run while the tab is visible.

The rolling observation cache retains up to 48 hours by receipt time, 24,000 rows and 48 MiB of image payloads. Save observation keeps a separate copy in Library → Documents. Saved copies participate in normal archive sync and its storage reserve. Session keys and rolling observations are device-local. The sample set includes attributed public reports and explicitly labelled practice points.
