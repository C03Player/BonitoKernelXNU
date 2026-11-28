# Camera (hosted)

## Linux side (works, 2026-11-28)

The mainline host drives both cameras (device tree `sdm670-google-common.dtsi`, `qcom-camss`): rear Sony IMX363 (4032x3024) with its lens
actuator, front IMX355 (3280x2464). On the booted image:

    cam-up                                              # load the drivers (host/initramfs/cam-up)
    camcap list                                         # the media graph
    camcap shot imx363 /tmp/rear.raw -n 20 -e 3000 -g 400
    camcap shot imx355 /tmp/front.raw -n 20 -e 3000 -g 400

`shot` (host/camcap.c) routes sensor, CSIPHY, CSID and a VFE raw interface and writes one frame of 10-bit packed Bayer samples; it prints
width, height, bytes per line and the fourcc. On the PC: `host/camraw.py FRAME W H BPL FOURCC OUT.png ROTATE` (90 for the rear camera, 270
for the front one). Verified by looking at the pictures: the rear camera showed what it was pointed at, the front camera, covered, showed
dim light and sensor noise. Not there: autofocus (the lens stays where it is), automatic exposure, the ISP (white balance and noise
reduction are crude, in the PC script). Pictures are private: they go to `logs/`, which git ignores.

## iOS side (open)

iOS reaches its cameras through Apple's ISP driver (`AppleH10CamIn`) and its firmware, which this system has nothing to stand in for: the
stock Camera app cannot use these cameras as it is.
