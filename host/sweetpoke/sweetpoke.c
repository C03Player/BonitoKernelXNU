// SPDX-License-Identifier: GPL-2.0
/*
 * sweetpoke: replace one instruction of the hosted system's code in RAM, found by the bytes around it.
 *   insmod sweetpoke.ko lo=0x100000000 hi=0x178000000 sig=<hex> at=<byte offset in sig> insn=<new instruction> [dry=1]
 * It scans [lo, hi) of physical memory, patches every match, and fails to load on purpose (nothing stays loaded).
 */
#include <linux/module.h>
#include <linux/mm.h>
#include <linux/hex.h>
#include <asm/barrier.h>

static unsigned long lo, hi;
static char *sig = "";
static int at, dry;
static uint insn = 0xd503201f;	/* nop */
module_param(lo, ulong, 0);
module_param(hi, ulong, 0);
module_param(sig, charp, 0);
module_param(at, int, 0);
module_param(insn, uint, 0);
module_param(dry, int, 0);

static int __init poke_init(void)
{
	u8 want[64];
	size_t n = strlen(sig) / 2;
	unsigned long pa, found = 0;

	if (n < 8 || n > sizeof(want) || hex2bin(want, sig, n) || at < 0 || at + 4 > n || (at & 3) || hi <= lo)
		return -EINVAL;
	for (pa = lo & PAGE_MASK; pa < hi; pa += PAGE_SIZE) {
		u8 *va;
		size_t off;

		if (!pfn_is_map_memory(pa >> PAGE_SHIFT))
			continue;
		va = phys_to_virt(pa);
		/* a match across two pages is not looked for */
		for (off = 0; off + n <= PAGE_SIZE; off += 4) {
			u32 *p = (u32 *)(va + off + at);

			if (*(u32 *)(va + off) != *(u32 *)want || memcmp(va + off, want, n))
				continue;
			found++;
			pr_info("sweetpoke: match at %#lx, instruction %08x -> %08x%s\n", pa + off + at, *p, insn, dry ? " (dry)" : "");
			if (dry)
				continue;
			WRITE_ONCE(*p, insn);
			asm volatile("dc cvau, %0\n dsb ish\n ic ialluis\n dsb ish\n isb\n" :: "r" (p) : "memory");
		}
		cond_resched();
	}
	pr_info("sweetpoke: %lu matches\n", found);
	return -EAGAIN;
}
module_init(poke_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("one-instruction patch of hosted code in RAM");
