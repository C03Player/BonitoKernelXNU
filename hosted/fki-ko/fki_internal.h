/* SPDX-License-Identifier: GPL-2.0-only */
/* Shared between fki's own files (not part of the interface in fki.h). */
#ifndef FKI_INTERNAL_H
#define FKI_INTERNAL_H
/* Run fn(arg) where Linux may run it (a Linux-compliant stack), keeping the caller's exception mask. */
void fki_linux_runs_ext(void (*fn)(void *), void *arg);
int fki_hostcall_init(void);
void fki_hostcall_exit(void);
#endif
