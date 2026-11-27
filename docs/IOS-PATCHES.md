# Patches to iOS's own code (hosted)

`host/iospatches.py` lists them; `host/mkboot.sh` turns the list into byte patches, and `xnu-run` applies those with `iospatch`
(`host/iospatch.c`) to the snapshot of the root disk before XNU starts. The changes live in RAM: the partition is never written.
`XNU_PATCH=0 xnu-run` starts iOS unchanged.

Each changed page also needs its SHA-256 in the cache file's code signature replaced. Without that, a process that touches the page loses
its signature's validity: SpringBoard then aborted about two minutes after boot in the privacy checks ("must contain an
NSHomeKitUsageDescription key"), in both boots tried. With the hash replaced, two boots (one soaked for 6 minutes) showed no such abort.

## The "123" key and the shifted keyboard (2026-11-27)

Symptoms: "123" did nothing, and a new keyboard sat 20 points to the right until the first touch.

Cause, measured in the running app: the `UIKeyboard` view was 320 points wide and the keyboard iOS wanted to give it 360 (the panel's
width in points). `-[UIKeyboard setFrame:]` treats a change of size as a reason to reload (`activate`). Every switch of the key plane asks
for the frame again, so the switch to the numbers happened, and the reload put the letters back
(`setKeyplaneName:` -> `_didChangeKeyplaneWithContext:` -> `setFrame:` -> `activate` -> ... -> `setToInitialKeyplane`).
Why the view starts 320 points wide was not traced.

Fix: one instruction, so that only a change of height reloads. Verified in Search and Safari: letters, "123", digits, "#+=", "ABC", emoji
and back, all in place. Not verified: rotation, other keyboard types, a height change.

## Stale text (2026-11-27)

Rows of lists showed other rows' text, a label showed the clock. iOS frees memory and gets the same address with other pages while the
Metal runtime still holds a GPU import of that address, and the runtime reused it. The call to that lookup in
`SweetMetal2` (a binary of the root disk, not the shared cache) becomes `mov x0, #0`. The patch is written for the plugin build on the
phone (21,603,472 bytes), which is newer than the one in the local disk image: `host/iospatches.py` says how to get such a file and its
device offsets.

## Screen brightness (2026-11-27)

The kernel's brightness service (`sweetbacklight=1`) stalls the display after a few frames, so iOS has no backlight device. Instead
`_BKSDisplayBrightnessSet`, which the Settings slider calls, branches to a routine placed in iPad-only code (`host/iosbright.py`) that
opens `/sweetbr<float bits in hex>`; the kernel prints it (`SWEET BRIGHTNESS`) and `host/initramfs/xnu-bright` sets the panel (level
squared, 4..1023). Verified: the Settings slider moved the panel from 1023 to 123 and back. Control Center disables its slider while
`BKSDisplayBrightnessIsBrightnessLevelControlAvailable` says no (it does without a backlight device); a second patch makes it say yes
(the user confirmed the slider works, patched in the running system). The panel starts at full brightness at each boot until a slider is moved.

## Finding such a fault

No debugger runs on the hosted iOS, but its code can be changed in RAM while it runs, and the kernel log reports every user crash with the
fault address.

1. Disassemble the suspect method from the shared cache (`bonito/tools/objc.py`, `dsc.py`).
2. Build `host/sweetpoke` (`make -C /usb/work/linux/out M=$PWD/host/sweetpoke ARCH=arm64 modules`) and copy the module to the phone's `/tmp`.
3. `host/iospoke.py on ADDR INSN` replaces an instruction, `off` restores it. It looks first and refuses a spot that matches many places
   (a function's first instructions do: one such patch hit 403). Code pages can be read from disk again, which drops a patch. Useful probes: `ldr xzr, [xN]` (`f940001f` for x0) crashes
   with the fault address equal to the register; `br xN` does the same for any value and shows that the place was reached. For a double,
   `fmov x9, dN` followed by `br x9` (the top byte of the address is not reported).
4. The app dies and restarts; read `sub 0x...` in the `CRASH` line (`host/klog.py` keeps only 10 minutes per run).
