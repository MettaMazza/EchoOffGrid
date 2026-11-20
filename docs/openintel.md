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

## Visual coverage in the next development build

Cameras & satellite imagery opens above the map. The offline directory indexes public camera feeds from Transport for London, Caltrans and Fintraffic, with an inventory date. Choose **Video cameras** for live players and clips or **Still cameras** for individual frames. Publisher-only viewers and satellite imagery have their own filters. Search by place or camera name, or narrow the chosen group by publisher. A listing indicates that the publisher advertised a camera when indexed. Its actual picture or stream may be unavailable. UK traffic clips, California HLS streams and Finnish stills are labelled separately. Aberdeen harbour’s four directions open the operator’s own viewers. Antarctic research station pictures come from the Australian Antarctic Program.

The gallery includes dated example images for offline use. Opening an image requests the publisher’s latest available file, or the selected UTC composite day for NASA. For regional Terra, Aqua and NOAA-20 imagery, select **Show on map** to overlay the retrieved image on the local basemap. GOES-East and GOES-West show full-disk Earth views. Save eligible retrieved images to Library for later offline access. Receiver predictions are calculated separately from orbital elements.

Open **Satellite orbits and passes** and search by spacecraft name or NORAD catalogue number. The bundled catalogue covers 256 objects from the CelesTrak stations, weather and Earth resources groups. Selecting an object calculates its predicted ground track and geometric pass times above 10° elevation for the selected region. Refresh the elements while online when they age. The app displays the element epoch and declines predictions from elements more than 14 days old.

### Investigations

Open **Investigations** to search the records already on this device by place name or text and inclusive UTC dates. Observation, feed, first retrieval and local file dates have different meanings. The result shows which date matched. Search covers local news, source snapshots, downloaded government documents, receiver imports and retained or saved OpenIntel observations. A missing record cannot establish what happened during a collection gap.

Create a case, select a result and choose **Save to case**. Expand a saved exhibit to inspect its source, date and digest. Files and available original images, captured news HTML and imported GeoJSON are preserved byte-for-byte. Older news and observations may only have an extract or normalised record. These are explicitly identified in search and in the exported citations. The per-file limit is 32 MiB. Explicitly saved case exhibits survive source cleanup.

**Export case ZIP** produces an offline package containing the exhibits, readable citations and a JSON manifest with SHA-256 hashes. Mac opens a save panel. On current Android versions the ZIP is saved in Downloads. A hash verifies that bytes match, independently of whether the source's claim is accurate.

### Cross-device case verification

On 19 November 2026 the installed Mac and Android review builds were tested with a separate Mac-origin and phone-origin case on each transport. The USB run used the paired TLS service through a USB port forward. The Wi-Fi run used the phone’s LAN address after the USB sync forward was removed. Both runs synced archive records while leaving media transfers out of the test.

Each case existed only on its originating device before transfer. Each contained a unique GeoJSON original and a PDF. All four cases retained their UUIDs. The Mac and Android exports matched for original file bytes, SHA-256 hashes, exhibit numbering, citation text and manifest exhibit metadata. Each device records its own export time.
