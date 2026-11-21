# EchoOffGrid

![EchoOffGrid offline workstation with a globe, books and a cassette](docs/echooffgrid.png)

**A library you can disconnect.** Open Wikipedia, find a word, read a saved article or pick a video from the shelf. EchoOffGrid keeps the files on your device and can sync a Mac and an Android phone when they meet again.

## Download public preview 5

| Device | Installer |
| --- | --- |
| Apple Silicon Mac · macOS 15 or later | [Download for Mac (.pkg)](https://github.com/MettaMazza/EchoOffGrid/releases/download/preview-5/EchoOffGrid.pkg) |
| arm64 Android · Android 9 or later | [Download for Android (.apk)](https://github.com/MettaMazza/EchoOffGrid/releases/download/preview-5/EchoOffGrid-arm64.apk) |

Move downloaded or imported titles between shelves, or delete them directly from the Library grid. With autoplay enabled, a series starts at episode one or resumes your latest episode on this device. Up Next follows episode order, and thumbnail bars show your progress.

On Android, downloads, audiobooks and Read Aloud can continue with the screen locked. Press Home or swipe up to go home during video playback to keep watching in a floating window. The upper-left menu opens every section. Tap the floating mint icon to launch your installed EchoLite app, or drag it to reposition it.

EchoOffGrid is in active development. [Installation notes and SHA-256 checksums](https://github.com/MettaMazza/EchoOffGrid/releases/tag/preview-5)

![Audiobook and game shelves in an earlier Mac development build](docs/library.png)

## OpenIntel

Explore aircraft, vessels, public cameras, satellite passes, Earth imagery, earthquakes and buoy readings on the offline map. Start with the bundled samples or choose a region and turn on live updates. Saved observations open from Library → Documents. [Coverage and offline use](docs/openintel.md)

## First launch

For the packaged preview, open **EchoOffGrid.pkg** on a Mac or install **EchoOffGrid-arm64.apk** on Android. Open **Wikipedia** and search for *ocean*. The preview packages include the Simple English Wikipedia mini archive, a starter English dictionary, a world overview map, illustrated field notes and sample media. The wiki contains article introductions. Larger ZIM collections can be connected separately. Each device can open its starter library before it is paired.

In the development builds, Home offers an illustrated Wikipedia edition on first launch. Select Simple English (2.9 GiB) or full English (118.7 GiB), or keep the included starter. **Devices** shows available storage and the 20 GB incoming-sync reserve.

| Open | What you can do |
| --- | --- |
| **Library** | Browse videos, shows, audio, books, pictures, documents, games and software. Open a category for its full grid, import personal files or browse publishers. Local videos have native playback controls and optional autoplay. |
| **News and Discover** | Read the illustrated field notes immediately. While connected, choose a regional news edition, refresh world news, and browse public catalogues. Saved articles and previously cached artwork stay on the device. |
| **Reference and maps** | Browse Wikipedia, look up highlighted words, explore a map and listen with the packaged English narrator. Map detail depends on the tile archives installed. |
| **History** | Zoom from eras to individual years, search the offline chronology and compare historical interpretations. [Sources and scope](vendor/history/NOTICE.md) |
| **OpenGov** | Browse national portals for 197 jurisdictions, search connected catalogues and save publications to Documents. |
| **OpenCorpo** | Search companies, funds and US foundations. Browse 233 jurisdictions and directories for ownership disclosures, capital and royal accounts. Save records to Library → Documents for offline reading. |
| **Private Browser** | External web links open through Tor. An optional Android phone VPN extends Tor routing to the native browser and other apps while EchoOffGrid is in the background. |
| **EchoLite** | The Mac hosts the supplied EchoLite interface. Android opens the independently installed EchoLite app and Back returns to EchoOffGrid. EchoLite owns its models and settings. |
| **Devices** | Pair a Mac and phone over USB and sync compatible content over USB or Wi-Fi. Import optional radio logs and compare local observations with public ScotMesh reports. |

## Exploring government records

Find official records in **OpenGov**, then choose **Save to Documents**. Choose among 197 jurisdictions to browse national portals and data catalogues. The default search combines World Bank Documents & Reports, GOV.UK statements and the US Federal Register. Use the country view to search official sites, browse linked publications or save a supported portal PDF or page. Previous results remain searchable on the device. The Library’s **Documents** shelf holds downloaded PDFs, readable statement text and your imported PDFs or text files. A scan of the 1941 Lend-Lease Act comes with the app. Live coverage depends on each publisher’s catalogue and availability.

## Exploring history

Browse from early stone tools to living memory on the offline **History** tab. Scroll the era rail, select an interval to zoom, enter a year in BCE or CE, or search across the local Wikipedia-derived chronology. **Guided history** explores selected turning points and competing interpretations. **Show all entries** opens the larger index. Open an entry’s Wikipedia article for context. [Sources and scope](vendor/history/NOTICE.md)

## Run the source preview on a Mac

Install Python 3.11 or newer with SQLite FTS5 support. From the checkout, run the following command. On first run it fetches and verifies about 506 MiB of Wikipedia data. Keep the terminal open and visit the localhost address it prints. The packaged Mac app includes the interpreter and the archive.

```sh
./Start-EchoOffGrid.command
```

For device pairing, Android build prerequisites and Mac installer details, see the [Android guide](docs/android.md) and [workstation guide](docs/workstation-guide.md).

## Next stage

**Peer-to-peer and mesh networking** is the next development stage. Today’s transport connects a paired Mac and phone directly. The proposed next step is exchanging selected offline content between trusted peers and testing what can reasonably travel over a low-bandwidth mesh. Multi-hop forwarding and radio-based library sync are planned work. [Networking roadmap](docs/roadmap.md)

## Help test

Try a cold launch with Wi-Fi off. Open an article, a map and a video, then tell us which device and build you used and the first step that failed. The Mac preview uses ad-hoc signing and the Android APK uses a local review key.

EchoOffGrid’s code uses the MIT licence. Bundled data, media and third-party tools retain their own terms. [Licence](LICENSE) · [Third-party notices](THIRD_PARTY.md)
