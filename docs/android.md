# Android companion

EchoOffGrid on Android runs the workstation server and the library on the phone. The Android WebView reads the phone's loopback address. Its Wikipedia archives, maps, films, shows, books, games, saved articles and neural reader remain available away from the Mac. The EchoLite tab opens the independently installed Android package. Android owns the transition into EchoLite and the return to the workstation.

## First launch

Install the arm64 review APK and open EchoOffGrid. First launch extracts the bundled runtime and Simple English Wikipedia mini archive to phone storage. Allow space for both the APK and its extracted assets. Search Wikipedia, browse the dictionary or open the world map before pairing. The sample books, photographs, illustrated field notes, game and video clips are local. The regional news feed and additional publisher downloads need an internet connection.

## Pair a Mac

Install the review APK on an arm64 Android device, open it once, and connect it by USB. Use Android's trusted-computer prompt. From the repository, run the following with the paths for your machine. The profile contains a private credential and belongs outside the checkout.

```sh
python3 android/pair.py --serial SERIAL --profile ~/echooffgrid-phone.json
python3 android/install-sync.py --profile ~/echooffgrid-phone.json --serial SERIAL \
  --adb /path/to/adb --host PHONE_WIFI_ADDRESS --kit "/path/to/OffGrid Kit" \
  --archive "$HOME/Library/Application Support/EchoOffGrid/archive.sqlite3" \
  --dictionary /path/to/dictionary.sqlite3
```

Reopen the phone app after first pairing to enable its paired-device foreground service. Both transports use the same authenticated TLS service. The Mac login item prefers USB and checks the local network when the cable is removed. Saved records and compatible media merge between peers. Mac bundles and installers stay on the Mac. Android packages stay off the Mac, and Android receives APKs with compatible arm64 or architecture-independent code. The worker checks ZIP contents to distinguish Mac bundles, ROM collections and browser games. Unrecognised program archives stay on their original device. The Mac supplies the portable kit and dictionary. Each device keeps its own queues and settings. Sync writes to a temporary file and verifies its SHA-256 digest before replacing a library file. Device status appears under **Devices**. Android's force-stop control stops its service until the app is opened again. The Mac uses Bonjour to find a paired phone on Wi-Fi and retains the configured address as a fallback.

To stop automatic sync on the Mac, run `launchctl bootout gui/$(id -u)/local.echooffgrid.companion-sync` and remove the corresponding plist from your LaunchAgents folder. Clearing the Android app's storage also removes its pairing and downloaded content.

## Build the review APK

Use JDK 21, SDK platform 36 and build tools 36.0.0, and an Android NDK with an arm64 API 28 compiler. Set `JAVA_HOME`, `ANDROID_HOME` and `ANDROID_NDK_HOME`. Set `SQLITE_SOURCE` to a SQLite amalgamation, `KIWIX_LIBS` to the Android arm64 Kiwix library set including the executable packaged as libkiwix-serve.so, `KIWIX_ICU_DATA` to the matching icudt data file from the Kiwix distribution, and `ECHO_COMPANION_ASSETS` to the installed workstation resource directory with the Gutenberg index and Narrator model.

Run `android/prepare-runtime.sh` followed by `android/build.sh`. The APK, local review signing key and build cache are under the ignored dist/android folder. Dependencies include CPython (PSF), SQLite (public domain), Kiwix tools and libkiwix (GPL), libzim (GPL), sherpa-onnx and its Kokoro model dependencies, and the VideoLAN LibVLC Android distribution. Keep their upstream notices with redistribution. The review signing key is local to this build machine.

## Device checks

Install the APK, build the separately signed test harness using `android/qa/build.sh` with the same local review key, install dist/android/qa/checks.apk and run `adb shell am instrument -w dev.echooffgrid.checks/.Checks`. These checks exercise an already populated kit, including local map data, search, media shelves, decoded previews and offline speech.

To check the integration with an existing EchoLite installation, run `adb shell am instrument -w -e bridge 1 dev.echooffgrid.checks/.Checks`. The test opens EchoLite from the library and uses Android Back to return. The media-only check uses `-e media 1` and exercises category grids, hover previews, local playback and advancing to the next video.

Open **More → OpenGov** to search official records. **Save to Documents** queues the file on the phone. Reopen it from **Library → Documents** after disconnecting. PDF and plain-text documents are compatible with both devices.

EchoOffGrid has a mint pixel-E launcher icon. On supported launchers, the first launch offers to pin the app to the home screen. You can also drag EchoOffGrid from the app drawer to the home screen.
