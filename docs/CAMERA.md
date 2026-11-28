# Camera (hosted)

## Linux side (works, 2026-11-28)

The mainline host drives both cameras (device tree `sdm670-google-common.dtsi`, `qcom-camss`): rear Sony IMX363 (4032x3024) with its lens
actuator, front IMX355 (3280x2464). On the booted image:

    cam-up                                              # load the drivers (host/initramfs/cam-up)
    camcap list                                         # the media graph
    camcap shot imx363 /tmp/rear.raw -n 20 -e 3000 -g 400
    camcap shot imx355 /tmp/front.raw -n 20 -e 3000 -g 400

`shot` (host/camcap.c) routes sensor, CSIPHY, CSID and a VFE raw interface and writes one frame of 10-bit packed Bayer samples; it prints
width, height, bytes per line and the fourcc. On the PC: `host/camraw.py FRAME W H BPL FOURCC OUT.png ROTATE` (90 for both cameras). Verified by looking at the pictures: the rear camera showed what it was pointed at, the front camera, covered, showed
dim light and sensor noise. Not there: autofocus (the lens stays where it is), automatic exposure, the ISP (white balance and noise
reduction are crude, in the PC script). Pictures are private: they go to `logs/`, which git ignores.

## iOS side

iOS reaches its cameras through Apple's ISP driver (`AppleH10CamIn`) and its firmware, which this system has nothing to stand in for:
Apple's Camera app, and apps that use the camera, cannot see these cameras. Instead:

- `camcap serve /tmp/xnucam` (started by `xnu-run`; `XNU_CAMERA=0` leaves the cameras out) switches a sensor on while asked, debayers one
  cell in four to an upright BGRA picture (rear 756x1008, front 616x820), sets exposure and gain towards a middle grey and a
  grey-world white balance, and writes into the camera file (layout: `host/camfile.h`). Measured: 30 frames per second, a few percent of a
  CPU. Off 5 s after the last request.
- `xnu.ko` (`cam=/tmp/xnucam`) and the kernel's `/dev/sweetcam` (`bsd/dev/linux64_cam.c`) give iOS read and write at offsets of that file.
- Our app `bonito/userland/camera` (workflow `camera-app`) shows the frames, flips between the cameras, and the shutter saves the picture
  on screen to Photos. Photos are the preview's size; there is no video, flash, focus or zoom.

Install into the test copy: send `/tmp/hfsreplay`, `/tmp/stockapps.sh` and `/tmp/camera-app.tar.gz` to the phone, then
`XNU_PRESTART=/tmp/stockapps.sh xnu-run`. Into the saved changes only on the user's say-so.

`host/camframe.py` turns a copy of the camera file into a PNG.

Tried on the phone (test copy, 2026-11-28): both cameras live in the app, Flip, the permission prompt, two photos saved to the library.

### Open: the rear stream stalls

At 4032x3024 the rear camera stops delivering frames every few seconds, with the sensor's controls left alone too, and without a line in
the kernel log; the front camera (3280x2464) ran 30 s without a stop, the rear one 6 s once under Linux alone. The server waits 250 ms,
then starts the stream again: about 26 frames a second with short hiccups. A memory-bandwidth vote in `qcom-camss` (it has none for
sdm670) did not change it.

Photos must not get a Metal device (`mtl2-clients`): with one it aborts as soon as the library holds a picture.
