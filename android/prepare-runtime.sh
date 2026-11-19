#!/usr/bin/env bash
# Retrieve pinned, upstream arm64 Android components into the ignored build cache.
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist/android
cd dist/android
fetch() {
    local name=$1 checksum=$2 url=$3
    if [ ! -f "$name" ]; then curl --fail --location --retry 2 "$url" -o "$name.part" && mv "$name.part" "$name"; fi
    echo "$checksum  $name" | shasum -a 256 -c -
}
fetch python.tar.gz 90bc78465ac0fef8493e21da2906434e1e596f5a8d1fc188e3c3611b34850c35 https://www.python.org/ftp/python/3.14.3/python-3.14.3-aarch64-linux-android.tar.gz
fetch sherpa.tar.bz2 5fb837e72c9dae6fe06d208dc97f2f6d715f7e5e476a6e36d1549e49c7e209d4 https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-v1.12.20-android.tar.bz2
fetch sherpa-api.h b575df36a35db0b384a708b05df968846af8c215ae5e9f3b76d35f31620d0ea3 https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.20/sherpa-onnx/c-api/c-api.h
fetch vlc.aar b48dab96e0e90e34cce3861963500c144a5aadb1b249d501d6a4b104d849e61b https://repo.maven.apache.org/maven2/org/videolan/android/libvlc-all/3.7.7/libvlc-all-3.7.7.aar
tar xzf python.tar.gz ./prefix
tar xjf sherpa.tar.bz2
mkdir -p vlc
unzip -qo vlc.aar 'jni/arm64-v8a/*' classes.jar -d vlc
