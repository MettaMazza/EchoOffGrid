#!/bin/bash
# Compile OffGrid Home with the EchoOffGrid dashboard bundled as a resource.
set -euo pipefail

project="$(cd -- "$(dirname -- "$0")" && pwd)"
name="OffGrid Home"
defines=()
if [[ "${1:-}" == "--standalone" ]]; then
    name="EchoOffGrid"
    defines=(-D ECHO_STANDALONE)
    shift
fi
kit="${1:-$(dirname "$project")/OffGrid Kit}"
source_file="$project/macos/OffGridHome.swift"
app="$kit/$name.app"
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
staged_app="$staging/$name.app"

contents="$staged_app/Contents"
resources="$contents/Resources/EchoOffGrid"
mkdir -p "$resources" "$contents/MacOS"
cp "$project/macos/Info.plist" "$contents/Info.plist"
if [[ "$name" == "EchoOffGrid" ]]; then
    /usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier local.echooffgrid.app' \
        -c 'Set :CFBundleName EchoOffGrid' \
        -c 'Delete :NSDesktopFolderUsageDescription' "$contents/Info.plist"
fi
for file in LICENSE THIRD_PARTY.md archive.py discovery.py catalog.json dashboard.py private_browser.py browser_proxy.py media_previews.py history_view.py govports.py government-portals.json opengov.py lend-lease-1941.pdf personal_library.py puzzle-mobile.html news.py publishers.py library_sources.py spotlight.py discover-starters.json world-population.json narrator.py reader.js workspace.css workspace.js atlas.html evidence.py kit_library.py references.py wiki_editions.py reading-words.txt puzzles.json; do
    cp "$project/$file" "$resources/$file"
done
cp "$project/android/storage_policy.py" "$resources/"
mkdir -p "$resources/vendor"
cp -R "$project/vendor/history" "$resources/vendor/"
cp -R "$project/vendor/starter-reference" "$project/vendor/starter-atlas" "$project/vendor/starter-notices" "$resources/vendor/"
wiki="$(python3 "$project/prepare-starter-wiki.py" "$project/dist/reference")"
install -m 644 "$wiki" "$resources/vendor/starter-reference/$(basename "$wiki")"
mkdir -p "$resources/vendor/private-browser"
cp -R "$project/vendor/private-browser/"{data,macos,notices} "$resources/vendor/private-browser/"
cp -R "$project/vendor/library-samples" "$project/vendor/picture-samples" "$project/vendor/puzzle-covers" "$resources/vendor/"
if [[ -n "${ECHO_LITE_REPOSITORY:-}" ]]; then
    "$project/package-echolite.sh" "$ECHO_LITE_REPOSITORY" \
        "$resources/EchoLite-source.zip" "${ECHO_LITE_REVISION:-HEAD}" > "$resources/EchoLite-revision.txt"
elif [[ "$name" == "EchoOffGrid" ]]; then
    cp "$project/vendor/EchoLite-source.zip" "$project/vendor/EchoLite-revision.txt" "$resources/"
fi
if [[ -f "$resources/EchoLite-source.zip" ]]; then
    cp "$project/setup-ernos.sh" "$project/vendor/Ernos-compiler-source.zip" \
        "$project/vendor/Ernos-compiler-sha256.txt" "$project/vendor/Ernos-revision.txt" "$resources/"
    cp "$project/setup-echolite.sh" "$project/prepare-echolite.sh" "$project/provision-echolite-assets.sh" \
        "$project/register-echolite-library.py" "$project/build-echolite-dictionary.py" "$resources/"
fi
if [[ -n "${ECHO_PYTHON_ARCHIVE:-}" ]]; then
    if [[ "$name" != "EchoOffGrid" || "$(uname -m)" != arm64 ]]; then
        echo "The pinned runtime is for standalone Apple Silicon builds." >&2
        exit 1
    fi
    pinned_sha=73f1ed14486aa278d331e95f7d6d452f5cfb69d90b418e26e62fd4846d53557d
    actual_sha="$(shasum -a 256 < "$ECHO_PYTHON_ARCHIVE")"
    if [[ "${actual_sha%% *}" != "$pinned_sha" ]]; then
        echo "The Python runtime does not match the pinned SHA-256." >&2
        exit 1
    fi
    runtime="$contents/Resources/PythonRuntime"
    mkdir -p "$runtime"
    tar -xzf "$ECHO_PYTHON_ARCHIVE" --strip-components 1 -C "$runtime"
    test -x "$runtime/bin/python3"
    test -f "$runtime/lib/python3.11/LICENSE.txt"
    cp -R "$project/vendor/python-notices" "$runtime/"
    "$runtime/bin/python3" -E -s -B -c 'import sqlite3, ssl; sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE search USING fts5(text)")'
fi
if [[ "$name" == "EchoOffGrid" ]]; then
    interface_source="${ECHO_INTERFACE_C:-}"
    if [[ -z "$interface_source" ]]; then
        interface_source="$staging/interface_compiled.c"
        gzip -dc "$project/vendor/EchoLite-interface.c.gz" > "$interface_source"
    fi
    clang -w -O2 -fwrapv -DEP_HAS_SQLITE -Dmain=echolite_entry -dynamiclib "$interface_source" -lsqlite3 -o "$contents/MacOS/EchoInterface.dylib"
fi
export CLANG_MODULE_CACHE_PATH="$staging/module-cache"
swiftc -parse-as-library -O -target "$(uname -m)-apple-macos15.0" "$project/macos/MakePoster.swift" -o "$resources/make-poster"
clang -fobjc-arc -c "$project/macos/MediaPlayer.m" -o "$staging/player.o"
swiftc -import-objc-header "$project/macos/MediaPlayer.h" "$staging/player.o" -framework Security -parse-as-library -O -target "$(uname -m)-apple-macos15.0" \
    ${defines[@]+"${defines[@]}"} "$source_file" -o "$contents/MacOS/OffGridHome"
codesign --force --sign - "$staged_app"
codesign --verify --strict "$staged_app"
mkdir -p "$kit"
ditto "$staged_app" "$app"
codesign --verify --strict "$app"
