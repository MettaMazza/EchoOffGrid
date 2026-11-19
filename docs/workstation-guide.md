# EchoOffGrid workstation guide

[Back to the project overview](../README.md)

EchoOffGrid brings offline media, reference works, maps, local EchoLite chat and public-source monitoring into one Mac window.
The source dashboard and archive use the Python standard library and SQLite
with FTS5. Hardware and SDRangel are optional.

## Install the Mac app

Open EchoOffGrid.pkg on an Apple Silicon Mac running macOS 15 or later. Open EchoOffGrid from your home Applications folder. This local review package is ad-hoc signed and has no Apple notarization.

Open a Library category and choose **Browse more**, or use **Browse catalogues** under Discover on Home. Tick titles across categories and pages, then choose **Download selections**. Open Downloads for progress and Library for saved titles. Browse the bundled Gutenberg book index offline. New media and software searches use Internet Archive and GitHub while connected. Rights vary by title and country. Software entries distinguish source downloads from the hand-picked Mac installers.

Choose **Set up EchoLite** to install the files required by the bundled EchoLite release. EchoLite manages its own chat preferences. The installer bundles the native tools. Initial setup needs internet for missing model and reference files. Existing matching Desktop EchoLite models can be reused after checksum verification. The installer also includes a Simple English Wikipedia mini ZIM, a reading dictionary, a world overview map, books, puzzles, photographs, field notes and video and audio samples. Open Wikipedia directly, including on an offline first launch.

The top Home cards rotate while open. You can scroll the other shelves, and their selections can change when you reopen Home. Hover or focus a video thumbnail for a short muted preview. The installer bundles Kokoro’s quantized English neural narrator. Highlight text to play a selection or use Read all at the top. The player supports pause, stop, seeking and playback speed. Text-based PDFs have a selectable text view.

Browse videos opens the complete Videos grid. The native player includes fullscreen, an Up next shelf and a persistent Autoplay switch. Other category pages also expand to grids.

Each Library collection links to its own catalogue. Open Software to discover source releases, installers and supported in-app tools. Download JSZip to inspect ZIP files inside the workstation. Devices groups receiver logs, ScotMesh reports and packet comparisons.

## Run the source dashboard on macOS

```sh
./Start-EchoOffGrid.command
```

Open the localhost address printed by the server. Choose regions, show sources,
then tick the sources to save. Once downloaded, use **Downloads → Open saved sources** to
browse the latest saved copy of each source, search snapshots, read saved
text, JSON or RSS/Atom feeds, and export original bytes, including while offline. Downloads
run in the background after you save your selection. The Downloads tab shows the
queue and the latest success or error. Reopen the app to resume any pending
downloads. Submit the saved selection again to retry completed attempts that
returned errors. The Sources screen also offers an opt-in hourly refresh
for selected data sources while the dashboard is open. Books are fetched on
request.

The default database lives under `~/Library/Application Support/EchoOffGrid`.
Use `--db PATH` to select another location. Source provenance and reuse terms
are included in the catalog. Saved content retains the original publisher’s
rights.

## Compare existing reception logs

Home and the radio views automatically import changed CSV and JSONL logs from
`01-Comms/Reception Logs` in the connected kit. Each archive retains the
observations it has already imported. For a log stored elsewhere, open **Receiver log**, choose a CSV or JSONL log, then click
**Import log**. You can also import multiple files from Terminal.

```sh
python3 evidence.py /path/to/receiver.jsonl /path/to/comparison.csv
```

Open **Compare packets** in the dashboard. The timeline shows the reported event time
and the time your recorder observed it, both in UTC. Imports are repeatable
and preserve each original record. Public observer feed activity and online
status are shown separately from local decoded packets. Importing or reviewing
logs requires no radio, SDRangel session, or internet access.

## Open from OffGrid Home

OffGrid Home 1.3 includes an **EchoOffGrid** shortcut on Home and Reference.
It starts the bundled dashboard on a free localhost port and opens it in the
default browser. Keep OffGrid Home open during a download or search session.
The shortcut uses macOS Command Line Tools Python at `/usr/bin/python3`.

With the existing OffGrid Kit next to this source directory, run
`./build-offgrid-home.sh` to rebuild the app and refresh its bundled dashboard.
Pass the kit directory as the first argument if it lives elsewhere.

## Build and package from source

The `macos/` directory contains the OffGrid Home Swift and bundle sources.
Run `./build-offgrid-home.sh "/path/to/OffGrid Kit"` on macOS 15 or later
with the Swift compiler to create an ad hoc signed app at that destination.
The EchoOffGrid dashboard is bundled. Companion OffGrid Kit assets such as
the atlas, Kiwix archives and media are supplied separately.

Run `./package-source.sh /path/to/EchoOffGrid-source.zip` to create a source
archive. It includes only project files and excludes downloads, the local
archive, radio evidence, and personal kit data.

Filter the packet timeline by source and UTC time. **From** includes the
specified time and **Before** excludes it. Routine public feed checks are
hidden by default so actual timestamp changes are easier to find.

If SDRangel is running locally on port 18891, use **Receiver log → Optional
radio → Capture receiver status** to save its current HackRF MeshCore
decoder report. Each snapshot gets the time EchoOffGrid observed it.
A packet already present in the decoder report may be from an earlier time.

Use **Export matching events as CSV** to save the displayed evidence results
with their UTC times, source labels and original records.

## Verify a source checkout

Run `python3 -B -m unittest -v` from the source directory. The release tests
use a temporary archive and fixture downloads. They cover multi-region setup,
search and export without network access, and evidence event classification.

GitHub Actions runs the release tests and verifies a fresh macOS build from
the extracted source package. The workflow uses fixture data and needs no
radio hardware or source credentials.

## Standalone macOS app

Run `./build-offgrid-home.sh --standalone /path/to/output` to build
`EchoOffGrid.app`. Open it to go directly to the in-app dashboard. It uses the same
local archive as the OffGrid Home shortcut and works without the companion
kit, maps, or radio. Keep the app open while downloads or local chat requests are running.
The build is ad hoc signed and uses macOS Command Line Tools Python.

To add public evidence without a radio, download **ScotMesh public network
snapshot** under Sources. Open **ScotMesh reports → Import a saved ScotMesh node**
and enter its exact map name. This reads the newest saved snapshot offline
and records the public packet feed and status timestamps separately.

PDFs and GIS ZIP packages are searchable by title and catalog description.
Open a saved copy in the archive to download the original file for your PDF
reader or GIS software.

Use **Downloads → Open saved sources → Download archive backup** to copy saved snapshots,
the search index and evidence to one SQLite file. Open a copy by running
`python3 dashboard.py --db /path/to/EchoOffGrid.sqlite3`. The exported copy
starts with no queued downloads and automatic refresh off. It retains the
source selection and does not change your current archive.

For a standalone Apple Silicon build with Python included, download the
[20261110 CPython 3.11.18 install-only archive](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110)
for `aarch64-apple-darwin`, then pass its path to the builder.

```sh
ECHO_PYTHON_ARCHIVE=/path/to/cpython-install_only.tar.gz \
  ./build-offgrid-home.sh --standalone /path/to/output
```

The builder checks the pinned SHA-256 before extraction and retains the
upstream installation and its included notices. This preview uses the
bundled interpreter without installing it into macOS. The source-only
build uses Command Line Tools Python.


## EchoLite companion

The standalone app includes the committed EchoLite source snapshot identified
in `vendor/EchoLite-revision.txt`. It includes the companion's MIT license,
third-party notices, and developer setup guide. Private state, local evidence,
models, reference-library downloads, and uncommitted development changes are
outside the source snapshot.

In the installed app, open **EchoLite → Set up EchoLite**. Choose **Use existing…** to connect an EchoLite installation, or **Install EchoLite** to provision the required files. EchoOffGrid hosts the supplied native interface in its window. The build instructions below apply to developers working from source.

To refresh the pinned snapshot, run `package-echolite.sh REPOSITORY OUTPUT.zip
REVISION` and update the archive and its revision record together. For a local
build from a different commit, set `ECHO_LITE_REPOSITORY` and optionally
`ECHO_LITE_REVISION` before building.

To build a second installation using already-provisioned assets, run:

```sh
./setup-echolite.sh "$HOME/EchoLite-companion" /path/to/prepared/EchoLite
```

The setup builds the pinned source with the installed Ernos compiler and links
the prepared model and reference directories. It creates a new application
and keeps its memory and credentials in the new installation. The original
development checkout remains the asset provider. Use the standalone
**EchoLite** menu to select the new `EchoLite.app`.

## Provision optional EchoLite assets

For a new asset directory, `./provision-echolite-assets.sh /path/to/assets`
fetches and checks the pinned llama.cpp, Kiwix and Raylib runtimes, generation model,
vision projector, and embedding model. Model files total about 3.45 GB.
The script keeps partial downloads for retry and checks each SHA-256 before
installing. It builds GMP 6.3.0 from verified GNU source using macOS
Command Line Tools. Pass `--runtimes-only` to skip model weights. Build or
select Ernos and register a reference library, then run `setup-echolite.sh`
against the completed asset directory.

To reuse an existing Wikipedia ZIM and prepared EchoLite dictionary database,
register them without duplicating the files:

```sh
python3 register-echolite-library.py /path/to/assets/library \
  /path/to/wikipedia.zim /path/to/dictionary.sqlite3
```

The destination must be new. The helper checks the dictionary schema and
records the ZIM's embedded identity, size and modification time. It creates
links to the chosen files, so keep those files accessible for offline use.

To create a starter dictionary from the public Simple English Wiktextract
dump, run `python3 build-echolite-dictionary.py /path/to/dictionary.sqlite3
--download-simple`. For broader coverage, download a Wiktextract JSONL or
JSONL.GZ dump from the [raw data page](https://kaikki.org/dictionary/rawdata.html)
and supply it with `--jsonl`. The builder indexes English records and stores
the source hash and attribution. Use its output with the library registration
helper. The generated database is not part of the source distribution.


## Build the Ernos toolchain locally

With Apple Command Line Tools and Rust/Cargo installed, build the pinned
driver without fetching Cargo dependencies:

```sh
./setup-ernos.sh /path/to/toolchain
ERNOS_COMPILER=/path/to/toolchain/ernos ERNOS_STDLIB=/path/to/toolchain/stdlib \
  ./setup-echolite.sh /path/to/EchoLite-companion /path/to/assets
```

This uses the bundled Ernos Rust driver source and its standard library.
It keeps the toolchain separate from your system and development installation.

## One-command EchoLite setup

With Apple Command Line Tools and Rust/Cargo available, choose a new
installation path and an asset directory:

```sh
./prepare-echolite.sh /path/to/EchoLite-companion /path/to/assets
```

The command builds the pinned compiler, fetches or verifies model and runtime
assets, creates a starter dictionary if needed, downloads and verifies the
530 MB Simple English Wikipedia ZIM, then builds and checks the native
companion. Pass an existing ZIM as the third argument to reuse that archive. Allow space for the approximately
3.45 GB of models if they aren't already in the asset directory. Keep the asset
directory and selected ZIM available after setup. The standalone EchoOffGrid
app can open the resulting `EchoLite.app`.

The GitHub verify workflow also builds the pinned Ernos compiler and EchoLite
with `--build-only`, then initializes and checks an isolated memory database.

The standalone **Library** opens video, audio, text books, guides and printable
maps directly from an existing OffGrid Kit. Use **Library → Choose OffGrid Kit**
to select another location. The app streams media and reads reference files
in place. Playback depends on the formats supported by macOS WebKit.

The standalone build compiles the native EchoLite interface from bundled C
source. Select a provisioned EchoLite installation in the app's EchoLite menu
to use its models, dictionary and Kiwix runtime. Select the OffGrid Kit from
the Library menu to connect its media, ZIM archives, atlas and browser puzzles.
These files stay in their existing locations.

For codecs that WebKit cannot play directly, use **Play with the in-app VLC player**
on the film or episode page. EchoOffGrid uses VideoLAN's signed macOS VLC app
bundled in the installer. Source builds can also use VLC from the kit or Applications. The embedded player provides
pause, seek and a return to the video page without converting the original file.
From the **EchoLite → Set up EchoLite** sheet, connect an existing installation
or install the companion and its required files under Application Support.

## Dictionary browsing

The default English reading list draws on lowercase words found in at least four of the 19 public-domain books used in the review kit, plus selected reference and technology terms. The index links to entries in your installed dictionary. Choose **Full dictionary** to browse initialisms, names, phrases and other entries. Direct lookup always searches the complete dictionary.

## Importing personal files

Open a category in **Library**, expand its Import control and select one or more files. Choose the original file or Mac app bundle. The importer uses available file metadata and embedded artwork. A repeat import of identical bytes into the same category uses the existing entry.

EPUB, text, PDF, supported audio and video, and self-contained HTML games open in the workstation. ROMs need a compatible emulator on the device. On Android, **Open with another app** gives your chosen app read access to that file. An imported APK also has **Launch installed app**. On the Mac, **Show file in Finder** selects the local copy. A selected Mac application bundle is stored as a ZIP to preserve its contents for transfer. Native programs run on their supported operating systems.

## Private Browser

Choose **Private Browser** (under **More** on a phone), select an exit location and press **Connect**. Once ready, choose **Open private browser**. The first page checks whether the connection uses Tor. Enter another HTTPS address and press **Go**. Use **Back** to revisit the prior page and **Done** to return to EchoOffGrid. **Disconnect** stops Tor.

Websites render in a separate browser view with a temporary browsing profile. The browser needs an internet connection. Only this view uses Tor. A country preference narrows the pool of exits, and signing in can identify you to a website.

## Building the populated preview

The Mac and Android builders use the same pinned 530,482,005-byte Wikipedia archive. They cache and verify it in `dist/reference`. For an offline build, set `ECHO_STARTER_ZIM` to a local copy of `wikipedia_en-simple_all_mini_2026-09.zim`. The Mac runtime includes its own Kiwix reader. A connected larger library takes precedence.

The source dashboard uses the bundled map, reading dictionary and starter shelves. The first-launch command downloads the ZIM before starting the server. The packaged apps also carry the narrator runtime and voice assets. EchoLite model downloads and pairing another device are optional setup steps. [Android companion](android.md) · [Networking roadmap](roadmap.md)
