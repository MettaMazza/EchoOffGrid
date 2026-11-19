#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
project=$PWD
out="$project/dist/android"
prefix="$out/prefix"
sdk="${ANDROID_HOME:?Set ANDROID_HOME to the Android SDK}"
ndk="${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to the NDK}"
build="$sdk/build-tools/36.0.0"
jar="$sdk/platforms/android-36/android.jar"
export PATH="${JAVA_HOME:?Set JAVA_HOME to JDK 21}/bin:$PATH"
cc=$(find "$ndk/toolchains/llvm/prebuilt" -name aarch64-linux-android28-clang | head -1)
lib="$out/package/lib/arm64-v8a"
mkdir -p "$lib" "$out/package/assets" "$out/classes" "$out/dex"
"$cc" -fPIC -shared android/workstation.c -I"$prefix/include/python3.14" -L"$prefix/lib" -lpython3.14 -o "$lib/libworkstation.so"
cp vendor/private-browser/android/libtor.so "$lib/"
cp "$prefix/lib/libpython3.14.so" "$prefix"/lib/lib*_python.so "$lib/"
if [ ! -f "$out/sqlite-fts5.so" ] || [ "$SQLITE_SOURCE" -nt "$out/sqlite-fts5.so" ]; then
"$cc" -fPIC -shared -O2 -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_COLUMN_METADATA -DSQLITE_ENABLE_DBSTAT_VTAB -DSQLITE_ENABLE_RTREE -DSQLITE_ENABLE_LOAD_EXTENSION=1 "${SQLITE_SOURCE:?Set SQLITE_SOURCE to the SQLite amalgamation}" -Wl,-soname,libsqlite3_python.so -lm -o "$out/sqlite-fts5.so"
fi
cp "$out/sqlite-fts5.so" "$lib/libsqlite3_python.so"
cp "$out/jniLibs/arm64-v8a/"{libonnxruntime,libsherpa-onnx-c-api}.so "$lib/"
"$cc" -shared -fPIC android/voice.c -I"$out" -L"$lib" -lsherpa-onnx-c-api -o "$lib/libvoice.so"
cp "$out/vlc/jni/arm64-v8a/"{libvlc,libvlcjni}.so "$lib/"
for name in kiwix-serve kiwix zim c++_shared; do cp "${KIWIX_LIBS:?Set KIWIX_LIBS to an Android arm64 Kiwix build}/lib$name.so" "$lib/"; done
python3 prepare-starter-wiki.py dist/reference
python3 - <<'PY'
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
out=Path('dist/android')
std=out/'prefix/lib/python3.14'
site=Path('lib/python3.14/site-packages')
with ZipFile(out/'package/assets/runtime.zip','w',ZIP_DEFLATED) as z:
    for p in std.rglob('*'):
        if p.is_file() and not {'__pycache__','test','tests','idlelib','ensurepip','tkinter'}.intersection(p.relative_to(std).parts):
            z.write(p,Path('lib/python3.14')/p.relative_to(std))
    for name in ('dashboard.py','private_browser.py','browser_proxy.py','media_previews.py','history_view.py','govports.py','government-portals.json','opengov.py','lend-lease-1941.pdf','personal_library.py','puzzle-mobile.html','references.py','wiki_editions.py','archive.py','news.py','publishers.py','library_sources.py','spotlight.py','discover-starters.json','world-population.json','discovery.py','evidence.py','narrator.py','kit_library.py','workspace.css','workspace.js','reader.js','atlas.html','puzzles.json','catalog.json','reading-words.txt'):
        z.write(name,site/name)
    for root in ("intel","vendor/openintel","vendor/history","vendor/starter-atlas", "vendor/starter-notices"):
        for p in Path(root).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts: z.write(p,site/p)
    for p in (Path("vendor/starter-reference/reading-dictionary.db"),
              Path("vendor/starter-reference/NOTICE.md")):
        z.write(p,site/p)
    wiki=Path("dist/reference/wikipedia_en-simple_all_mini_2026-09.zim")
    z.write(wiki,site/"vendor/starter-reference"/wiki.name)
    for p in [*Path('vendor/picture-samples').glob('*'), *Path('vendor/library-samples').glob('*')]:
        z.write(p,site/p)
    for p in [*Path('vendor/private-browser/data').glob('*'),*Path('vendor/private-browser/notices').glob('*')]:
        z.write(p,site/p)
    for p in Path('vendor/puzzle-covers').glob('*.png'):
        z.write(p,site/p)
    for name in ('mobile.py','storage_policy.py','compatibility.py','merge.py','peer.py','voice.py'):
        z.write(Path('android')/name,site/name)
    import os
    icu=Path(os.environ['KIWIX_ICU_DATA'])
    z.write(icu,site/'icu'/icu.name)
    assets=Path(os.environ['ECHO_COMPANION_ASSETS'])
    z.write(assets/'gutenberg-index.csv.gz',site/'gutenberg-index.csv.gz')
    model=assets/'Narrator/model'
    for p in model.rglob('*'):
        if p.is_file():
            z.write(p,site/'model'/p.relative_to(model))
    z.write('/etc/ssl/cert.pem',site/'cacert.pem')
PY
"$build/aapt2" compile --dir android/res -o "$out/launcher-res.zip"
"$build/aapt2" link -I "$jar" -R "$out/launcher-res.zip" --manifest android/AndroidManifest.xml -o "$out/base.apk"
javac --release 8 -classpath "$jar:$out/vlc/classes.jar:$project/vendor/private-browser/android/webkit-1.9.0.jar" -d "$out/classes" android/*.java
jar cf "$out/main.jar" -C "$out/classes" .
"$build/d8" --min-api 28 --lib "$jar" --output "$out/dex" "$out/main.jar" "$out/vlc/classes.jar" "$project/vendor/private-browser/android/webkit-1.9.0.jar"
cp "$out/base.apk" "$out/unsigned.apk"
cp "$out/dex/classes.dex" "$out/package/"
(cd "$out/package" && zip -q -r "$out/unsigned.apk" lib assets classes.dex)
"$build/zipalign" -f -p 4 "$out/unsigned.apk" "$out/aligned.apk"
key="$out/review.jks"
if [ ! -f "$key" ]; then
    (umask 077; keytool -genkeypair -keystore "$key" -storepass android -keypass android -alias review -dname 'CN=EchoOffGrid Local Review' -keyalg RSA -validity 3650)
fi
# Use complete APK installs. A failed ADB incremental stream can remove the installed app.
rm -f "$out/EchoOffGrid.apk.idsig"
"$build/apksigner" sign --v4-signing-enabled false --ks "$key" --ks-pass pass:android --out "$out/EchoOffGrid.apk" "$out/aligned.apk"
"$build/apksigner" verify "$out/EchoOffGrid.apk"
