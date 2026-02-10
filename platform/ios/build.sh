#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team

# Fail out on error
set -eux -o pipefail

IOS_ARCH="arm64"
IOS_VERSION="15.0"
IOS_PLATFORM="iphoneos"
HOST_PATH=""

GIT_ROOT=$(git rev-parse --show-toplevel)
DEP_PREFIX="$GIT_ROOT/third_party/deps"

usage() {
  echo "Usage: $0 --project-name <project-name> [options]"
  echo "Options:"
  echo "  --project-name <project-name>   Name of the project (required)"
  echo "  --dep-prefix <dep-prefix>       Dependency prefix (default: third_party/deps)"
  echo "  --arch <arch>                   Architecture (arm64 or x86_64)"
  echo "  --ios-version <ios-version>     iOS version (default: 15.0)"
  echo "  --host-path <host-path>         Host Qt path (optional)"
  echo "  --help, -h                      Show this help message"
}

while (($# > 0)); do
  case $1 in
    --project-name)
      PROJECT_NAME=$2
      shift 2
      ;;
    --dep-prefix)
      DEP_PREFIX=$2
      shift 2
      ;;
    --arch)
      IOS_ARCH=$2
      shift 2
      ;;
    --ios-version)
      IOS_VERSION=$2
      shift 2
      ;;
    --host-path)
      HOST_PATH=$2
      shift 2
      ;;
    --help | -h)
      usage
      exit 1
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unexpected argument $1"
      usage
      exit 1
      ;;
  esac
done

if [ -z "${PROJECT_NAME+x}" ]; then
  echo "--project-name is a required argument"
  usage
  exit 1
fi

if [[ "$IOS_ARCH" == "iphonesimulator-"* ]]; then
  IOS_PLATFORM="iphonesimulator"
  CMAKE_ARCH="${IOS_ARCH#iphonesimulator-}"
elif [[ "$IOS_ARCH" == "ios-"* ]]; then
  IOS_PLATFORM="iphoneos"
  CMAKE_ARCH="${IOS_ARCH#ios-}"
else
  # Fallback for simple architecture strings
  CMAKE_ARCH="$IOS_ARCH"
  if [[ "$IOS_ARCH" == "x86_64" ]]; then
    IOS_PLATFORM="iphonesimulator"
  fi
fi

readonly BIN_NAME="$PROJECT_NAME-$IOS_ARCH-$IOS_VERSION.ipa"
CMAKE="$DEP_PREFIX/qt/bin/qt-cmake"
PREFIX_PATH="$DEP_PREFIX"

# Build project.
ccache --zero-stats

# We use the Xcode generator for iOS to ensure proper bundle structure.
# CODE_SIGNING_ALLOWED=NO allows us to build in CI without a developer cert.
# ONLY_ACTIVE_ARCH=NO ensures we build for the specified architecture.
EXTRA_CMAKE_ARGS=()
if [ -f "platform/ios/Info.plist" ]; then
  EXTRA_CMAKE_ARGS+=("-DCMAKE_MACOSX_BUNDLE_INFO_PLIST=$(realpath platform/ios/Info.plist)")
fi

if [ -n "$HOST_PATH" ]; then
  EXTRA_CMAKE_ARGS+=("-DQT_HOST_PATH=$HOST_PATH")
fi

"$CMAKE" \
  -DCMAKE_CXX_FLAGS="-isystem/usr/local/include" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_SYSROOT="$IOS_PLATFORM" \
  -DCMAKE_OSX_ARCHITECTURES="$CMAKE_ARCH" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="$IOS_VERSION" \
  -DCMAKE_PREFIX_PATH="$PREFIX_PATH" \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY="" \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO \
  -DCMAKE_XCODE_ATTRIBUTE_DEBUG_INFORMATION_FORMAT="dwarf" \
  -DCMAKE_XCODE_ATTRIBUTE_ONLY_ACTIVE_ARCH=NO \
  "${EXTRA_CMAKE_ARGS[@]}" \
  -G Xcode \
  -B_build \
  "$@" \
  .

cmake --build _build --config Release

# Packaging into IPA
mkdir -p _build/Payload
# Search for the .app bundle. Xcode output paths can vary depending on project structure.
APP_BUNDLE=$(find "_build/Release-$IOS_PLATFORM" -name "*.app" -type d | head -n 1)
if [ -z "$APP_BUNDLE" ]; then
  echo "Could not find .app bundle in _build/Release-$IOS_PLATFORM"
  exit 1
fi

cp -r "$APP_BUNDLE" _build/Payload/
pushd _build
zip -r "../$BIN_NAME" Payload
popd

ccache --show-stats

# Check if the binary exists.
if [[ ! -s "$BIN_NAME" ]]; then
  echo "There's no $BIN_NAME!"
  exit 1
fi

# Create a sha256 checksum.
shasum -a 256 "$BIN_NAME" >"$BIN_NAME".sha256
