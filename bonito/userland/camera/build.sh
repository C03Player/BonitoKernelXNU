#!/bin/sh
# Build the camera app for iOS 16 arm64 (on macOS) into out/BonitoCamera.app, signed ad hoc.
set -e
cd "$(dirname "$0")"
A=out/BonitoCamera.app
rm -rf out && mkdir -p $A
xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=16.0 -fobjc-arc -O2 -Wall -framework UIKit -framework Foundation \
	-framework CoreGraphics -framework QuartzCore -o $A/BonitoCamera main.m
cp Info.plist $A/
plutil -convert binary1 $A/Info.plist
python3 mkicon.py $A/Icon@2x.png 120
python3 mkicon.py $A/Icon@3x.png 180
codesign -f -s - $A
codesign -dvv $A 2>&1 | head -5
ls -la $A
