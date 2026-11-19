#!/bin/bash
# Package a built workstation with a clean, precompiled EchoLite companion.
set -euo pipefail
project="$(cd "$(dirname "$0")" && pwd)"
app="${1:?Specify EchoOffGrid.app}"
companion="${2:?Specify a clean compiled EchoLite checkout}"
runtime="${3:?Specify the provisioned models/runtime directory}"
output="${4:?Specify a new release directory}"
kit="${5:?Specify the source OffGrid Kit for starter assets}"
mkdir "$output"
output="$(cd "$output" && pwd)"
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
template="$stage/EchoLite"
mkdir -p "$template/models" "$template/bin"
for file in LICENSE THIRD_PARTY.md EchoLite.app config; do ditto "$companion/$file" "$template/$file"; done
ln -s bin/echolite-launch "$template/echolite"
for tool in core runtime ui launch pdf docx process image browser; do
    cp "$companion/bin/echolite-$tool" "$template/bin/"
done
for directory in llama-b12359 kiwix-tools_macos-arm64-3.8.2 notices; do
    ditto "$runtime/$directory" "$template/models/runtime/$directory"
done
for dylib in libraylib.dylib libgmp.10.dylib; do cp "$runtime/$dylib" "$template/models/runtime/"; done
ditto "$app" "$output/EchoOffGrid.app"
vlc="$kit/Apps/VLC.app"
codesign --verify --deep --strict -R='anchor apple generic and identifier "org.videolan.vlc" and certificate leaf[subject.OU] = "75GAHG3SZQ"' "$vlc"
mkdir -p "$output/EchoOffGrid.app/Contents/Helpers"
ditto "$vlc" "$output/EchoOffGrid.app/Contents/Helpers/VLC.app"
dest="$output/EchoOffGrid.app/Contents/Resources/EchoOffGrid"
"$output/EchoOffGrid.app/Contents/Resources/PythonRuntime/bin/python3" -B "$project/package-voice.py" "${ECHO_VOICE_CACHE:-$stage/voice-cache}" "$dest/Narrator"
starter="$dest/Starter Kit"
puzzles="04-Entertainment/Games/Browser Puzzles"
mkdir -p "$starter/$puzzles" "$starter/04-Entertainment/Books"
"$output/EchoOffGrid.app/Contents/Resources/PythonRuntime/bin/python3" - "$dest/puzzles.json" "$kit/$puzzles" "$starter/$puzzles" <<'PYTHON'
import hashlib,json,shutil,sys
from pathlib import Path
for name,checksum in json.loads(Path(sys.argv[1]).read_text()).items():
    source=Path(sys.argv[2])/name
    if hashlib.sha256(source.read_bytes()).hexdigest()!=checksum:
        raise SystemExit("Puzzle file does not match the reviewed version: "+name)
    shutil.copyfile(source,Path(sys.argv[3])/name)
PYTHON
for title in "Alice’s Adventures in Wonderland" "Pride and Prejudice" "The Adventures of Sherlock Holmes"; do
    cp "$kit/04-Entertainment/Books/$title.txt" "$starter/04-Entertainment/Books/"
done
ditto "$project/vendor/starter-notices" "$starter/Notices"
index="${ECHO_GUTENBERG_INDEX:-$stage/gutenberg-index.csv.gz}"
if [[ ! -f "$index" ]]; then
    curl --fail --location --retry 2 --output "$index" https://gutenberg.pglaf.org/cache/epub/feeds/pg_catalog.csv.gz
fi
gzip -t "$index"
cp "$index" "$dest/gutenberg-index.csv.gz"
ditto -c -k --keepParent "$template" "$dest/companion-runtime.zip"
codesign --force --sign "${ECHO_CODESIGN_IDENTITY:--}" "$output/EchoOffGrid.app"
codesign --verify --deep --strict "$output/EchoOffGrid.app"
mkdir "$stage/payload"
ditto "$output/EchoOffGrid.app" "$stage/payload/EchoOffGrid.app"
pkgbuild --analyze --root "$stage/payload" "$stage/components.plist"
/usr/libexec/PlistBuddy -c 'Set :0:BundleIsRelocatable false' "$stage/components.plist"
pkgbuild --root "$stage/payload" --component-plist "$stage/components.plist" --install-location /Applications --identifier local.echooffgrid.workstation --version "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist")" "$stage/workstation.pkg"
productbuild --synthesize --package "$stage/workstation.pkg" "$stage/distribution.xml"
sed -i '' 's|<options |<domains enable_anywhere="false" enable_currentUserHome="true" enable_localSystem="false"/><options |' "$stage/distribution.xml"
productbuild --distribution "$stage/distribution.xml" --package-path "$stage" "$output/EchoOffGrid.pkg"
