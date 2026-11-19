#!/bin/bash
# Compile the pinned Ernos driver into a project-local toolchain.
set -euo pipefail

project="$(cd -- "$(dirname -- "$0")" && pwd)"
output="${1:?Usage: setup-ernos.sh NEW_TOOLCHAIN_DIRECTORY}"
case "$output" in /*) ;; *) output="$PWD/$output" ;; esac
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "This EchoLite toolchain targets Apple Silicon macOS." >&2
    exit 1
fi
if [[ -e "$output" || -L "$output" ]]; then
    echo "Choose a new toolchain directory." >&2
    exit 1
fi
if ! xcrun --find clang >/dev/null 2>&1 || ! command -v cargo >/dev/null; then
    echo "Apple Command Line Tools and Rust/Cargo are needed to build Ernos." >&2
    exit 1
fi

vendor="$project/vendor"
if [[ ! -r "$vendor/Ernos-compiler-source.zip" ]]; then
    vendor="$project"
fi
archive="$vendor/Ernos-compiler-source.zip"
expected="$(cat "$vendor/Ernos-compiler-sha256.txt")"
digest="$(shasum -a 256 < "$archive")"
if [[ "${digest%% *}" != "$expected" ]]; then
    echo "The Ernos source archive does not match its pinned checksum." >&2
    exit 1
fi

parent="$(dirname -- "$output")"
mkdir -p "$parent"
stage="$(mktemp -d "$parent/.ernos-build.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
unzip -q "$archive" -d "$stage"
(
    cd "$stage/Ernos"
    CARGO_HOME="$stage/cargo" cargo build --release --locked --offline --target-dir "$stage/target"
)
mkdir "$stage/toolchain"
cp "$stage/target/release/ernos" "$stage/toolchain/ernos"
cp -R "$stage/Ernos/stdlib" "$stage/toolchain/"
cp "$stage/Ernos/LICENSE" "$vendor/Ernos-revision.txt" "$stage/toolchain/"
cat > "$stage/hello.ep" <<'PROGRAM'
define main:
    display "EchoOffGrid Ernos driver ready"
    return 0
PROGRAM
(
    cd "$stage"
    "$stage/toolchain/ernos" hello.ep
)
if [[ ! -x "$stage/hello" || "$("$stage/hello")" != "EchoOffGrid Ernos driver ready" ]]; then
    echo "The built compiler failed its executable check." >&2
    exit 1
fi
if [[ -e "$output" || -L "$output" ]]; then
    echo "The toolchain directory became occupied during the build." >&2
    exit 1
fi
mv -n "$stage/toolchain" "$output"
test ! -e "$stage/toolchain"
printf 'Ernos toolchain: %s\n' "$output"
