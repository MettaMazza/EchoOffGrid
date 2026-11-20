# Third-party notices

## EchoLite

The pinned companion source is distributed under its own MIT license.
Its license and dependency notices are included inside
`vendor/EchoLite-source.zip`. The exact source commit is listed in
`vendor/EchoLite-revision.txt`.

The public snapshot omits two upstream development notes that contain workstation-specific paths. The project packages the pinned code and licences.

The embedded interface is compiled from the generated C source in
`vendor/EchoLite-interface.c.gz`. It was regenerated from committed EchoLite
revision `d154dffda4280fe027be1ef70ccc84618e2547b5` with the development
Ernos compiler. The interface uses the same MIT license. The bundled
provisioning scripts retain their separately pinned companion revision.

## Portable Python

Portable Apple Silicon builds may include CPython 3.11.18 from the
[20261110 Python Build Standalone release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110).
The app retains the interpreter distribution's installed notices. The
additional native dependency notices in `vendor/python-notices` come from
`python/licenses` in the corresponding full build archive. That archive
was checked against upstream SHA-256
`5ee82bbad0ca0c7cb355da0b19fbd6d37b384b5849b4d2839336cdc6f6983824`.

## Catalog content

Source attribution and rights are listed with each catalog entry and preserved
in the archive. Downloaded data and books are supplied by their publishers.


## Optional EchoLite libraries

The provisioning script retrieves Raylib and GMP from their publishers.
It saves their license notices in the local asset directory. GNU GMP is
compiled locally from the verified source archive.


## Ernos compiler

The bundled Ernos compiler source is MIT-licensed, with its original license
inside the archive. The source revision and archive checksum are recorded
next to the ZIP in `vendor/`.

## Installer content

The installer contains a Project Gutenberg metadata index and three Gutenberg texts with their original notices. The Starter Kit Notices folder contains the notices for Simon Tatham’s puzzles, MapLibre, PMTiles and the starter basemap data. The precompiled EchoLite folder includes its LICENSE and THIRD_PARTY.md and the vendored runtime notices. Discovery shows publisher-reported terms for each selection.

The macOS installer includes the signed VideoLAN VLC 3.0.24 app, with its original resources and notices. EchoOffGrid loads its playback libraries for local video. [VideoLAN release files and corresponding VLC source](https://download.videolan.org/pub/videolan/vlc/3.0.24/).

## Offline narration

The packaged reader includes the Kokoro 82M v1.0 quantized ONNX model and voice embeddings under Apache-2.0. It uses the Emma British English voice with the sherpa-onnx 1.12.30 CPU runtime. The model package supplies pronunciation data from eSpeak NG. Model and runtime distribution notices travel with the assets. The release packaging script pins and verifies the model archive and runtime wheels. [Kokoro models and attribution](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html).

## Starter library and companion

The preview packages include a Kiwix Simple English Wikipedia mini archive, a condensed Wiktionary reading dictionary and an offline overview atlas. Wikipedia and Wiktionary contributors, Kiwix, OpenStreetMap, Protomaps and the map library authors retain their respective notices. [Reference credits](vendor/starter-reference/NOTICE.md) · [Map data](vendor/starter-notices/map-data.txt) · [Map rendering](vendor/starter-notices/basemaps.txt)

The starter shelves use *Dracula* (Gutenberg #345), a LibriVox opening excerpt from *A Scandal in Bohemia*, and short Blender Foundation previews from *Big Buck Bunny* and *Caminandes 2*. The Big Buck Bunny preview is CC BY 3.0. The Caminandes preview credits the Blender Foundation and Caminandes team. Photographs are individually credited in the app. The original EchoOffGrid field notes accompany those photos. [Picture authors, sources and licences](vendor/picture-samples/credits.json)

Private Browser uses the Tor Project tools on Mac and the Guardian Project's tor-android build on Android. The Android WebView bridge uses AndroidX WebKit. The arm64 companion also uses CPython, SQLite, Android Kiwix libraries, sherpa-onnx and VideoLAN LibVLC. [Browser component provenance and licences](vendor/private-browser/notices/origins.txt) · [Android build inputs](android/prepare-runtime.sh)

The bundled Lend-Lease Act is the US Government Publishing Office scan of 55 Stat. 31 (1941). [Original PDF](https://www.govinfo.gov/content/pkg/STATUTE-55/pdf/STATUTE-55-Pg31.pdf). OpenGov also indexes government publications on demand. Individual publishers’ reuse notices apply to downloaded material.

The national portal directory uses factual addresses from [UN DESA’s e-government portal directory](https://ekap.desa.un.org/Resources), supplemented with four jurisdiction entries or addresses. External sites control their content and availability.

The offline History index adapts English Wikipedia text under CC BY-SA 4.0. Article identifiers and attribution travel with the database. [History sources and licence](vendor/history/NOTICE.md)

## OpenIntel

The pure Python components of [sgp4 2.25](https://pypi.org/project/sgp4/2.25/) and [websockets 13.1](https://pypi.org/project/websockets/13.1/) are distributed under MIT and BSD-3-Clause respectively. Their licence texts are in vendor/openintel. Fintraffic data is supplied by Fintraffic / Digitraffic under [CC BY 4.0](https://www.digitraffic.fi/en/terms-of-service/). Aircraft records are supplied by adsb.lol under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Earthquake and buoy samples credit USGS and NOAA respectively. Provider links, dates and access types appear in the OpenIntel catalogue and observation details.

The development camera directory contains public location and feed metadata from [Transport for London](https://tfl.gov.uk/info-for/open-data-users/), [Caltrans Commercial Wholesale Web Portal](https://cwwp2.dot.ca.gov/documentation/cctv/cctv.htm) and [Fintraffic / Digitraffic](https://www.digitraffic.fi/en/terms-of-service/). Powered by TfL Open Data. The offline example pictures credit NASA GIBS, NOAA NESDIS STAR and the USGS Hawaiian Volcano Observatory. Source URLs and retrieval dates accompany the images in intel/previews/sources.json.

## OpenCorpo

The register directory adapts the [GLEIF Registration Authorities List v1.9](https://www.gleif.org/lei-data/code-lists/gleif-registration-authorities-list/2026-09-30_ra-list-v1.9.csv). The included [Berkshire Hathaway legal entity record](https://api.gleif.org/api/v1/lei-records/5493000C01ZX7D35SD85) is a GLEIF API snapshot retrieved 19 November 2026. US foundation search uses [ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/api). Linked reports credit their respective publishers.

Android phone VPN uses hev-socks5-tunnel at commit 4702e9ad2815f3a04e2af63b2e7eb36e861c9c86 with its pinned submodules. Build with Android NDK ndk-build, APP_BUILD_SCRIPT=Android.mk, NDK_APPLICATION_MK=Application.mk, APP_ABI=arm64-v8a and APP_PLATFORM=android-28. See vendor/private-browser/notices/hev-tunnel.txt.
