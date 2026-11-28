/*
 * The camera file shared by the host's camera server (host/camcap.c "serve") and iOS's camera app (bonito/userland/camera) through
 * /dev/sweetcam. Little endian. The app writes the request; the server writes pixels into the two slots in turn and then the state.
 */
#include <stdint.h>

#define CAMF_REQUEST    0                       /* struct camf_request */
#define CAMF_STATE      4096                    /* struct camf_state */
#define CAMF_PIXELS     8192                    /* slot n at CAMF_PIXELS + n * CAMF_SLOT: width * height BGRA pixels, upright */
#define CAMF_SLOT       0x400000
#define CAMF_SIZE       (CAMF_PIXELS + 2 * CAMF_SLOT)
#define CAMF_QMAGIC     0x514d4143u             /* "CAMQ" */
#define CAMF_SMAGIC     0x464d4143u             /* "CAMF" */

struct camf_request {
	uint32_t magic, camera;                 /* 0: off, 1: rear, 2: front */
	uint32_t beat;                          /* counted up while the app wants frames: standing still for 5 s switches the camera off */
};

struct camf_state {
	uint32_t magic, seq;                    /* seq counts the frames written */
	uint32_t slot, width, height, camera;   /* where the newest one is, its size, and its camera */
};
