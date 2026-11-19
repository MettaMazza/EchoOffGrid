#!/bin/bash
# Provision a fresh EchoLite companion using a local or downloaded Wikipedia ZIM.
set -euo pipefail

project="$(cd -- "$(dirname -- "$0")" && pwd)"
output="${1:?Usage: prepare-echolite.sh NEW_INSTALLATION ASSET_ROOT [WIKIPEDIA.zim]}"
assets="${2:?Specify an asset directory}"
zim="${3:-}"
case "$output" in /*) ;; *) output="$PWD/$output" ;; esac
if [[ -e "$output" || -L "$output" ]]; then
    echo "Choose a new EchoLite installation path." >&2
    exit 1
fi
if [[ -n "$zim" && ( ! -r "$zim" || ! -f "$zim" || "$zim" != *.zim ) ]]; then
    echo "Choose a readable Wikipedia ZIM file." >&2
    exit 1
fi
if [[ -n "$zim" ]]; then
    zim="$(cd -- "$(dirname -- "$zim")" && pwd -P)/$(basename -- "$zim")"
fi

python=/usr/bin/python3
if [[ -x "$project/../PythonRuntime/bin/python3" ]]; then
    python="$project/../PythonRuntime/bin/python3"
fi
if [[ -z "${SSL_CERT_FILE:-}" && -r /etc/ssl/cert.pem ]]; then
    export SSL_CERT_FILE=/etc/ssl/cert.pem
fi
mkdir -p "$assets"
assets="$(cd -- "$assets" && pwd -P)"
toolchain="$assets/toolchain"

prebuilt="$project/companion-runtime.zip"
if [[ ! -f "$prebuilt" && ( ! -x "$toolchain/ernos" || ! -d "$toolchain/stdlib" ) ]]; then
    "$project/setup-ernos.sh" "$toolchain"
fi
if [[ -f "$prebuilt" ]]; then
    "$project/provision-echolite-assets.sh" "$assets" --models-only
else
    "$project/provision-echolite-assets.sh" "$assets"
fi
if [[ ! -e "$assets/library" ]]; then
    if [[ -z "$zim" && -f "$project/vendor/starter-reference/wikipedia_en-simple_all_mini_2026-09.zim" ]]; then
        zim="$project/vendor/starter-reference/wikipedia_en-simple_all_mini_2026-09.zim"
    fi
    if [[ -z "$zim" ]]; then
        "$project/provision-echolite-assets.sh" "$assets" --starter-wikipedia-only
        zim="$assets/references/wikipedia_en-simple_all_mini_2026-09.zim"
    fi
    dictionary="$assets/dictionary-starter.sqlite3"
    if [[ ! -f "$dictionary" ]]; then
        "$python" -E -s -B "$project/build-echolite-dictionary.py" "$dictionary" --download-simple
    fi
    "$python" -E -s -B "$project/register-echolite-library.py" "$assets/library" "$zim" "$dictionary"
elif [[ -n "$zim" ]]; then
    "$python" -E -s -B - "$assets/library" "$zim" <<'PY'
import json
from pathlib import Path
import sys

library = Path(sys.argv[1])
manifest = json.loads((library / "wikipedia.json").read_text())
archive = library / manifest["file"]
if not archive.samefile(sys.argv[2]):
    sys.exit("The existing asset library points to a different ZIM. Use a new asset root or select its registered file.")
PY
fi
if [[ -f "$prebuilt" ]]; then
    stage="$(mktemp -d "$(dirname "$output")/.echolite-install.XXXXXX")"
    trap 'rm -rf -- "$stage"' EXIT
    ditto -x -k "$prebuilt" "$stage"
    mkdir -p "$stage/EchoLite/models/native"
    for name in Qwen3.5-4B-Q4_K_M.gguf mmproj-Qwen3.5-4B-Q8_0.gguf all-minilm-l6-v2_f16.gguf; do
        ln -s "$assets/models/native/$name" "$stage/EchoLite/models/native/$name"
    done
    ln -s "$assets/library" "$stage/EchoLite/library"
    test -x "$stage/EchoLite/bin/echolite-ui"
    test -x "$stage/EchoLite/echolite"
    mv -n "$stage/EchoLite" "$output"
    test ! -e "$stage/EchoLite"
else
    ERNOS_COMPILER="$toolchain/ernos" ERNOS_STDLIB="$toolchain/stdlib" \
        "$project/setup-echolite.sh" "$output" "$assets"
fi
export ECHOLITE_HOME="$output/data"
export ECHOLITE_NATIVE_TOKEN_FILE="$output/data/native-runtime.token"
"$output/echolite" init
"$output/echolite" doctor
