"""Compiles services/pkhex ahead of time for Android (linux-bionic-arm64) into jniLibs, where Android
installs it as an executable file. Needs the .NET 10 SDK and the Android NDK."""
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sdk = Path(os.environ.get('ANDROID_HOME', Path.home() / 'Library/Android/sdk'))
ndk = Path(os.environ.get('ANDROID_NDK_HOME') or max((sdk / 'ndk').iterdir()))
toolchain = next((ndk / 'toolchains/llvm/prebuilt').iterdir())
out = HERE / 'build' / 'pkhex'
subprocess.run(['dotnet', 'publish', str(ROOT / 'services/pkhex/pkhex.csproj'), '-c', 'Release',
                '-r', 'linux-bionic-arm64', '-o', str(out),
                '-p:PublishAot=true', '-p:PublishSingleFile=false', '-p:EnableCompressionInSingleFile=false',
                '-p:DisableUnsupportedError=true', '-p:PublishAotUsingRuntimePack=true',
                f'-p:CppCompilerAndLinker={toolchain}/bin/clang', f'-p:SysRoot={toolchain}/sysroot',
                f'-p:ObjCopyName={toolchain}/bin/llvm-objcopy', '-p:LinkerFlavor=lld'], check=True)
target = HERE / 'jniLibs' / 'arm64-v8a' / 'libpokeldn_pkhex.so'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(out / 'pokeldn-pkhex', target)
print('PKHeX helper for Android:', target)
