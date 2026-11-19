#!/bin/bash
# Build a separate EchoLite installation using already-provisioned local assets.
set -euo pipefail

project="$(cd -- "$(dirname -- "$0")" && pwd)"
output="${1:?Usage: setup-echolite.sh NEW_INSTALLATION ASSET_ROOT|--build-only}"
assets="${2:?Specify an asset root or --build-only}"
case "$output" in /*) ;; *) output="$PWD/$output" ;; esac
compiler="${ERNOS_COMPILER:-$HOME/.local/bin/ernos}"
stdlib="${ERNOS_STDLIB:-$HOME/.local/bin/stdlib}"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "The EchoLite companion requires Apple Silicon macOS." >&2
    exit 1
fi
if [[ -e "$output" || -L "$output" ]]; then
    echo "Choose a new installation path." >&2
    exit 1
fi
if [[ "$assets" != --build-only ]]; then
    assets="$(cd -- "$assets" && pwd -P)"
    for file in \
        models/native/Qwen3.5-4B-Q4_K_M.gguf \
        models/native/mmproj-Qwen3.5-4B-Q8_0.gguf \
        models/native/all-minilm-l6-v2_f16.gguf \
        models/runtime/llama-b12359/llama-server \
        models/runtime/kiwix-tools_macos-arm64-3.8.2/kiwix-serve \
        models/runtime/libraylib.dylib models/runtime/libgmp.10.dylib \
        library/wikipedia.json library/dictionary.sqlite3; do
        if [[ ! -r "$assets/$file" ]]; then
            echo "Missing EchoLite asset: $file" >&2
            exit 1
        fi
    done
fi
if [[ ! -x "$compiler" || ! -d "$stdlib" ]]; then
    echo "Install the Ernos compiler and standard library, or set ERNOS_COMPILER and ERNOS_STDLIB." >&2
    exit 1
fi
compiler="$(cd -- "$(dirname -- "$compiler")" && pwd -P)/$(basename -- "$compiler")"
stdlib="$(cd -- "$stdlib" && pwd -P)"
parent="$(dirname -- "$output")"
mkdir -p "$parent"
staging="$(mktemp -d "$parent/.echolite-build.XXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
archive="$project/vendor/EchoLite-source.zip"
if [[ ! -r "$archive" ]]; then
    archive="$project/EchoLite-source.zip"
fi
/usr/bin/unzip -q "$archive" -d "$staging"
checkout="$staging/EchoLite"
mkdir -p "$checkout/EchoLite.app/Contents/MacOS"
ln -s "$stdlib" "$checkout/stdlib"
if [[ "$assets" != --build-only ]]; then
    ln -s "$assets/models" "$checkout/models"
    ln -s "$assets/library" "$checkout/library"
fi
(
    cd "$checkout"
    export ERNOS_COMPILER="$compiler"
    "$compiler" src/build.ep
    ./src/build
)
test -x "$checkout/EchoLite.app/Contents/MacOS/EchoLite"
if [[ -e "$output" || -L "$output" ]]; then
    echo "The installation path became occupied during the build." >&2
    exit 1
fi
mv -n "$checkout" "$output"
test ! -e "$checkout"
printf 'EchoLite app: %s/EchoLite.app\n' "$output"
