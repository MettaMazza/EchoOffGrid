#!/bin/bash
# Package the release files without archives, radio logs or downloaded assets.
set -euo pipefail
project="$(cd -- "$(dirname -- "$0")" && pwd)"
output="${1:?Usage: package-source.sh OUTPUT.zip}"
case "$output" in /*) ;; *) output="$PWD/$output" ;; esac
if [[ "$output" != *.zip || -e "$output" ]]; then
    echo "Choose a new .zip output path." >&2
    exit 1
fi
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
mkdir -p "$staging/EchoOffGrid/macos" "$staging/EchoOffGrid/.github/workflows" "$staging/EchoOffGrid/vendor"
for file in build-history-index.py prepare-starter-wiki.py Start-EchoOffGrid.command .gitignore AGENTS.md LICENSE README.md THIRD_PARTY.md archive.py discovery.py dashboard.py private_browser.py browser_proxy.py media_previews.py history_view.py govports.py government-portals.json opengov.py opencorpo.py corporate-registers.json corporate-starter.json lend-lease-1941.pdf personal_library.py puzzle-mobile.html news.py publishers.py library_sources.py spotlight.py discover-starters.json world-population.json narrator.py reader.js workspace.css workspace.js atlas.html evidence.py kit_library.py references.py wiki_editions.py reading-words.txt puzzles.json catalog.json test_storage_policy.py test_wiki_editions.py test_workstation.py test_openintel.py test_private_browser.py test_library_imports.py test_download_recovery.py \
    build-offgrid-home.sh package-installer.sh package-voice.py package-source.sh package-echolite.sh setup-echolite.sh prepare-echolite.sh setup-ernos.sh provision-echolite-assets.sh register-echolite-library.py build-echolite-dictionary.py macos/MakePoster.swift macos/MediaPlayer.h macos/MediaPlayer.m macos/Info.plist macos/OffGridHome.swift .github/workflows/verify.yml \
    vendor/EchoLite-interface.c.gz vendor/EchoLite-source.zip vendor/EchoLite-revision.txt \
    vendor/Ernos-compiler-source.zip vendor/Ernos-compiler-sha256.txt vendor/Ernos-revision.txt; do
    cp -p "$project/$file" "$staging/EchoOffGrid/$file"
done
mkdir -p "$staging/EchoOffGrid/android/qa"
cp -R "$project/android/res" "$staging/EchoOffGrid/android/"
cp "$project"/android/*.{py,java,c,sh,xml} "$staging/EchoOffGrid/android/"
cp "$project"/android/qa/*.{java,js,py,sh,xml} "$staging/EchoOffGrid/android/qa/"
cp -R "$project/docs" "$staging/EchoOffGrid/"
cp -R "$project/vendor/private-browser" "$project/vendor/library-samples" "$project/vendor/picture-samples" "$project/vendor/puzzle-covers" "$staging/EchoOffGrid/vendor/"
cp -R "$project/intel" "$staging/EchoOffGrid/"
cp -R "$project/vendor/openintel" "$staging/EchoOffGrid/vendor/"
cp -R "$project/vendor/history" "$staging/EchoOffGrid/vendor/"
cp -R "$project/vendor/starter-reference" "$project/vendor/starter-atlas" "$staging/EchoOffGrid/vendor/"
cp -R "$project/vendor/starter-notices" "$staging/EchoOffGrid/vendor/"
cp -R "$project/vendor/python-notices" "$staging/EchoOffGrid/vendor/"
cd "$staging"
zip -qr "$output" EchoOffGrid
