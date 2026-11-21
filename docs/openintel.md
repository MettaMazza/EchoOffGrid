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

Open **Compare dated satellite imagery** and choose a sensor and two UTC days. The comparison first looks for both images on this device. If a day is missing, **Fetch and save image** retrieves that day for the selected region and keeps the image in the library. Each panel shows its composite day, retrieval time, projection and publisher link. A composite can contain clouds or gaps and can combine several observation times.

Select a retained aircraft or Fintraffic vessel and choose **View report history**. Reports are ordered by observed time and include the retrieved time when available. During replay, the history ends at the selected replay time. Intervals longer than 15 minutes are marked as gaps and the map breaks its trail there. History includes permanently saved observations after the rolling cache expires. AISStream is a live-only source.

### Investigations

In **Investigations → Landmark clues**, download an OpenStreetMap extract for the selected regional centre. Search its names and tags offline for clues such as piers, harbours, lighthouses or railway stations in a roughly 16 km by 16 km area. **Search visible map** also searches features rendered from the local map tiles at the current zoom without downloading an extract. **Show on map** places a marker at the mapped point or feature centre. **Save to case** preserves the original extract, the selected feature’s identifier and version, and its map edit and retrieval dates. The edit date tells you when the map record changed. A feature’s existence on a particular historical day requires independent evidence. Aberdeen uses the Britain and Ireland Overpass server, with worldwide mirrors available if the regional request fails. When edit metadata is unavailable, the exhibit records the retrieval date and identifies it as such. The device retains the most recent 12 regional extracts. Case exhibits survive removal of an extract.

Under **Investigations**, **Observation coverage** shows how many distinct local records each source has for the selected region between two UTC times. The end time is exclusive. A saved copy counts once, including after its temporary copy expires.

Open **Investigations** to search the records already on this device by place name or text and inclusive UTC dates. Observation, feed, first retrieval and local file dates have different meanings. The result shows which date matched. Search covers local news, source snapshots, downloaded government documents, receiver imports and retained or saved OpenIntel observations. A missing record cannot establish what happened during a collection gap.

Create a case, select a result and choose **Save to case**. Expand a saved exhibit to inspect its source, date and digest. Files and available original images, captured news HTML and imported GeoJSON are preserved byte-for-byte. Older news and observations may only have an extract or normalised record. These are explicitly identified in search and in the exported citations. The per-file limit is 32 MiB. Explicitly saved case exhibits survive source cleanup.

**Export case ZIP** produces an offline package containing the exhibits, readable citations and a JSON manifest with SHA-256 hashes. Mac opens a save panel. On current Android versions the ZIP is saved in Downloads. A hash verifies that bytes match, independently of whether the source's claim is accurate.

### Cross-device case verification

On 19 November 2026 the installed Mac and Android review builds were tested with a separate Mac-origin and phone-origin case on each transport. The USB run used the paired TLS service through a USB port forward. The Wi-Fi run used the phone’s LAN address after the USB sync forward was removed. Both runs synced archive records while leaving media transfers out of the test.

Each case existed only on its originating device before transfer. Each contained a unique GeoJSON original and a PDF. All four cases retained their UUIDs. The Mac and Android exports matched for original file bytes, SHA-256 hashes, exhibit numbering, citation text and manifest exhibit metadata. Each device records its own export time.

On 20 November 2026, a second test used the draft and made Aberdeen Harbour Revision Order 2016 PDFs from legislation.gov.uk. The Mac-origin case reached the REDMAGIC over paired USB. During a separate Wi-Fi round trip, a new Mac finding reached the phone and a phone-origin capture of the harbour order reached the isolated Mac library. The exports agreed on the two PDF originals, citations, findings and relationship. The phone capture’s viewport, rendered HTML and readable text reopened with matching hashes. The Mac paused incoming records below the 20 GB reserve before the user authorised the isolated test. The temporary exception was removed immediately afterwards.

The Mac WebKit and REDMAGIC checks also opened five lighthouse matches in the Aberdeen extract and displayed the two locally saved Terra composites for 1 and 2 June 2024. Separate case-screen checks created a finding with supporting and contradicting exhibits, recorded an uncertain relationship and reopened both in the timeline. Report-history tests used synthetic aircraft and vessel observations to verify publisher attribution and a 30-minute gap.

In a case, open **Record a reviewed relationship** to connect two named entities. Enter the relationship, select its saved exhibit, record a passage or page and mark the relationship supported, disputed or uncertain. The review appears on the timeline. Export includes the relationship, its assessment and a citation to the preserved exhibit.

While viewing a page in **Private Browser**, choose **Capture to case** on Mac or **Capture page to case** on Android. Review the page address, choose an existing case or name a new one, and select **Save to case**. The case stores the visible viewport image, the browser’s rendered HTML and any readable page text, with a capture timestamp and a separate SHA-256 hash for each exhibit. The HTML records the document as rendered. Scripts, network responses, linked files and media streams require separate evidence. Export writes the HTML as plain text so it can be inspected offline.
