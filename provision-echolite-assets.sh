#!/bin/bash
# Download the pinned models and published macOS runtime archives for EchoLite.
set -euo pipefail
root="${1:?Usage: provision-echolite-assets.sh ASSET_ROOT [--runtimes-only|--starter-wikipedia-only]}"
mode="${2:-all}"
if [[ "$mode" != all && "$mode" != --runtimes-only && "$mode" != --models-only && "$mode" != --starter-wikipedia-only ]]; then
    echo "Expected --runtimes-only, --starter-wikipedia-only, or no second argument." >&2
    exit 1
fi
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "EchoLite's pinned runtimes require Apple Silicon macOS." >&2
    exit 1
fi
mkdir -p "$root"
root="$(cd -- "$root" && pwd -P)"
cache="$root/.downloads"
mkdir -p "$cache"
lock="$cache/pull.lock"
if ! mkdir "$lock"; then
    echo "The asset root already has a download lock at $lock." >&2
    exit 1
fi
trap 'rmdir "$lock"' EXIT

verified() {
    local file="$1" digest="$2" bytes="$3" actual
    [[ -f "$file" ]] || return 1
    if [[ -n "$bytes" && "$(stat -L -f %z "$file")" != "$bytes" ]]; then return 1; fi
    actual="$(shasum -a 256 < "$file")"
    [[ "${actual%% *}" == "$digest" ]]
}

download() {
    local url="$1" destination="$2" digest="$3" bytes="${4:-}" partial
    if [[ -e "$destination" || -L "$destination" ]]; then
        if ! verified "$destination" "$digest" "$bytes"; then
            echo "Existing file does not match the pinned checksum: $destination" >&2
            return 1
        fi
        printf 'Verified %s\n' "$destination"
        return
    fi
    mkdir -p "$(dirname -- "$destination")"
    if [[ "$destination" == "$root/models/native/"* ]]; then
        local existing="${ECHO_REUSE_MODEL_DIR:-$HOME/Desktop/EchoLite/models/native}/${destination##*/}"
        if verified "$existing" "$digest" "$bytes"; then
            ln "$existing" "$destination" 2>/dev/null || cp "$existing" "$destination"
            printf 'Reused verified local model %s\n' "$destination"
            return
        fi
    fi
    partial="$destination.part"
    if [[ -L "$partial" ]]; then
        echo "Download partial must not be a symlink: $partial" >&2
        return 1
    fi
    if ! verified "$partial" "$digest" "$bytes"; then
        /usr/bin/curl --fail --location --retry 2 --connect-timeout 20 \
            --continue-at - --output "$partial" "$url"
    fi
    if ! verified "$partial" "$digest" "$bytes"; then
        mv -n "$partial" "$partial.invalid"
        echo "Downloaded bytes did not match the pinned checksum: $destination" >&2
        return 1
    fi
    mv -n "$partial" "$destination"
    printf 'Verified %s\n' "$destination"
}

if [[ "$mode" == --starter-wikipedia-only ]]; then
    name=wikipedia_en-simple_all_mini_2026-09.zim
    download "https://download.kiwix.org/zim/wikipedia/$name" "$root/references/$name" \
        a6a56861f8dedca2e2434d921c61c74e552c80310623173b1ec31e80ce1a692e 530482005
    exit 0
fi

install_runtime() {
    local url="$1" directory="$2" executable="$3" digest="$4" archive staging
    archive="$cache/${url##*/}"
    download "$url" "$archive" "$digest"
    if [[ -e "$root/models/runtime/$directory" ]]; then
        test -x "$root/models/runtime/$directory/$executable"
        return
    fi
    mkdir -p "$root/models/runtime"
    staging="$(mktemp -d "$root/models/runtime/.unpack.XXXXXX")"
    if ! tar -xzf "$archive" -C "$staging" || ! test -x "$staging/$directory/$executable"; then
        rm -rf "$staging"
        echo "The runtime archive did not contain $directory/$executable." >&2
        return 1
    fi
    mv -n "$staging/$directory" "$root/models/runtime/$directory"
    rm -rf "$staging"
    printf 'Installed %s\n' "$directory"
}

install_raylib() (
    local destination="$root/models/runtime/libraylib.dylib"
    if [[ -e "$destination" ]]; then
        lipo "$destination" -verify_arch arm64
        return
    fi
    local archive="$cache/raylib-6.2_macos.tar.gz" staging
    download https://github.com/raysan5/raylib/releases/download/6.2/raylib-6.2_macos.tar.gz \
        "$archive" 100437734a44d56ed9d2a1c4b249dbfc6d6cc3477a45e306f9f56fe5f1e2b4ef
    staging="$(mktemp -d "$cache/.raylib.XXXXXX")"
    trap 'rm -rf -- "$staging"' EXIT
    tar -xzf "$archive" -C "$staging"
    local library="$staging/raylib-6.2_macos/lib/libraylib.6.2.0.dylib"
    lipo "$library" -verify_arch arm64
    mkdir -p "$root/models/runtime/notices/raylib"
    cp "$staging/raylib-6.2_macos/LICENSE" "$root/models/runtime/notices/raylib/"
    mv -n "$library" "$destination"
    printf 'Installed Raylib 6.2\n'
)

install_gmp() (
    local destination="$root/models/runtime/libgmp.10.dylib"
    if [[ -e "$destination" ]]; then
        lipo "$destination" -verify_arch arm64
        return
    fi
    local archive="$cache/gmp-6.3.0.tar.xz" staging
    download https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz \
        "$archive" a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898
    # GMP libtool splits an installation prefix containing spaces.
    staging="$(mktemp -d /private/tmp/echooffgrid-gmp.XXXXXX)"
    trap 'rm -rf -- "$staging"' EXIT
    tar -xf "$archive" -C "$staging"
    cd "$staging/gmp-6.3.0"
    printf 'Building GMP 6.3.0 from its verified source archive…\n'
    if ! (./configure --prefix="$staging/prefix" --disable-static --enable-shared &&
          make -j 2 && make install) >"$cache/gmp-build.log" 2>&1; then
        tail -30 "$cache/gmp-build.log" >&2
        return 1
    fi
    local library="$staging/prefix/lib/libgmp.10.dylib"
    lipo "$library" -verify_arch arm64
    install_name_tool -id @rpath/libgmp.10.dylib "$library"
    codesign --force --sign - "$library"
    mkdir -p "$root/models/runtime/notices/gmp"
    cp COPYING* "$root/models/runtime/notices/gmp/"
    # The installed name is a symlink inside the build stage.
    cp -L "$library" "$staging/libgmp.10.dylib"
    mv -n "$staging/libgmp.10.dylib" "$destination"
    printf 'Installed GMP 6.3.0\n'
)

if [[ "$mode" != --models-only ]]; then
install_runtime https://github.com/ggml-org/llama.cpp/releases/download/b12359/llama-b12359-bin-macos-arm64.tar.gz \
    llama-b12359 llama-server 82b00abc740160e1b9980e6cc79c117345fa34af058c80e6c0a69aa8ddccde75
install_runtime https://download.kiwix.org/release/kiwix-tools/kiwix-tools_macos-arm64-3.8.2.tar.gz \
    kiwix-tools_macos-arm64-3.8.2 kiwix-serve 5c64d43176627e558a117146b02ea36b7da2b0cd3a332cbff075cde05d9585f9
install_raylib
install_gmp
fi
if [[ "$mode" == all || "$mode" == --models-only ]]; then
    qwen=https://huggingface.co/ggml-org/Qwen3.5-4B-GGUF/resolve/8d43d974efc48399cb58957ad49c8b26bf5a109c
    download "$qwen/Qwen3.5-4B-Q4_K_M.gguf" "$root/models/native/Qwen3.5-4B-Q4_K_M.gguf" \
        217002fa8008ef4fc6d548353a3aebef055a96e6ff8e0e2c0953ef8254a89c14 3032091584
    download "$qwen/mmproj-Qwen3.5-4B-Q8_0.gguf" "$root/models/native/mmproj-Qwen3.5-4B-Q8_0.gguf" \
        5a5ba634d46f9888599963bfc52194eadf099e1efdbee46d71957d911cf62654 366894560
    download https://huggingface.co/LLukas22/all-MiniLM-L6-v2-GGUF/resolve/ae6369f25f3393dcca54ff7b41157ffd2e43e2e6/all-minilm-l6-v2_f16.gguf \
        "$root/models/native/all-minilm-l6-v2_f16.gguf" \
        7266519c8c9b860e99d561d2cb849cf546b248eb23bcb23787be5b11180daec3 46220288
fi
echo "Pinned downloads verified. See EchoLite's setup guide for Ernos and the reference library."
