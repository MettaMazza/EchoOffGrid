#!/bin/bash
# Package committed EchoLite source without touching the development checkout.
set -euo pipefail
repository="${1:?Usage: package-echolite.sh REPOSITORY OUTPUT.zip [REVISION]}"
output="${2:?Choose a new .zip output path}"
revision="${3:-HEAD}"
case "$output" in /*) ;; *) output="$PWD/$output" ;; esac
if [[ "$output" != *.zip || -e "$output" ]]; then
    echo "Choose a new .zip output path." >&2
    exit 1
fi
commit="$(git -C "$repository" rev-parse --verify --end-of-options "$revision^{commit}")"
git -C "$repository" cat-file -e "$commit:src/echolite.ep"
git -C "$repository" cat-file -e "$commit:LICENSE"
git -C "$repository" archive --format=zip --prefix=EchoLite/ --output="$output" "$commit" -- \
    LICENSE THIRD_PARTY.md CONTRIBUTING.md README.md README.txt \
    docs config src tests build echolite EchoLite.app/Contents/Info.plist \
    ':(exclude)docs/Library-Sources.txt' ':(exclude)docs/Release-Gates.txt'
printf '%s\n' "$commit"
