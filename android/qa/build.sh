#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/../.."
out="$PWD/dist/android/qa"
mkdir -p "$out/classes" "$out/dex"
build="$ANDROID_HOME/build-tools/36.0.0"
jar="$ANDROID_HOME/platforms/android-36/android.jar"
export PATH="$JAVA_HOME/bin:$PATH"
javac --release 8 -classpath "$jar" -d "$out/classes" android/qa/Checks.java
jar cf "$out/classes.jar" -C "$out/classes" .
"$build/d8" --min-api 28 --lib "$jar" --output "$out/dex" "$out/classes.jar"
"$build/aapt2" link -I "$jar" --manifest android/qa/AndroidManifest.xml -o "$out/check.apk"
mkdir -p "$out/test-assets/assets"
cp vendor/library-samples/show.mp4 android/qa/{cases,geography,series-playback}.js "$out/test-assets/assets/"
(cd "$out/test-assets" && zip -q "$out/check.apk" assets/cases.js assets/geography.js assets/series-playback.js assets/show.mp4)
(cd "$out/dex" && zip -q "$out/check.apk" classes.dex)
"$build/zipalign" -f 4 "$out/check.apk" "$out/aligned.apk"
"$build/apksigner" sign --ks dist/android/review.jks --ks-pass pass:android --out "$out/checks.apk" "$out/aligned.apk"
