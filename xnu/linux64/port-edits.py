#!/usr/bin/env python3
# The manual part of the port: run in the xnu tree after `git apply --reject` of cf3399e patches 0001/0006/0007 (rejects moved to ../rej).
# Record of how 9001-linux64-xnu8796.patch was made; later fixes are edited in the patch tree directly.
import re, sys
def sub(f, old, new, count=1):
    s = open(f).read()
    assert s.count(old) >= 1, (f, old)
    s = s.replace(old, new, count)
    open(f, 'w').write(s)
# arm_init: include, secondary entry, assert report
f='osfmk/arm/arm_init.c'
def include(f, after):
    s = open(f).read()
    if '#include <linux64/linux64.h>' not in s:
        sub(f, after, after + '#include <linux64/linux64.h>\n')
include(f, '#include <debug.h>\n') if '#include <debug.h>\n' in open(f).read() else include(f, '#include <mach/mach_types.h>\n')
sub(f,'__startup_func\nvoid\narm_init(\n','''/*
 * LINUX64 (xnulinux): where a secondary CPU starts (LINUX64_CALL_CPU_START), on the host's thread for that CPU, in
 * its own world (the host's page tables, which hold XNU's kernel mappings; XNU's keys). start_cpu's work on hardware
 * (MMU, vectors, stacks) is the host's; arm_init_cpu sets the thread pointer and goes on into the scheduler.
 */
void arm_init_cpu(cpu_data_t *cpu_data_ptr, uint64_t hib_header_phys);
void linux64_cpu_entry(cpu_data_t *cpu_data_ptr) __attribute__((noreturn));
void
linux64_cpu_entry(cpu_data_t *cpu_data_ptr)
{
	arm_init_cpu(cpu_data_ptr, 0);
	__builtin_unreachable();
}

/* LINUX64: a failed assert() while hosted (see kern/assert.h); the host may end the run. */
void
linux64_assert_report(const char *file, int line, const char *expr)
{
	struct linux64_assert_info a = { file, line, expr };
	linux64_call(LINUX64_CALL_ASSERT, &a);
}

__startup_func
void
arm_init(
''')
# rtclock
sub('osfmk/arm/rtclock.c','\tunsigned int             user_mode;\n\tuintptr_t                pc;\n','\tunsigned int             user_mode;\n\tuintptr_t                pc;\n\tlinux64_count(LINUX64_CTR_RTCLOCK);\t/* LINUX64: for the host\'s monitor */\n')
# virtual interrupt flag
rej=open('../rej/osfmk/arm/machine_routines_common.c.rej').read()
h=rej.split('\n@@')[1] if rej.count('\n@@')>1 else rej[rej.index('\n@@')+3:]
block='\n'.join(l[1:] for l in h.split('\n')[1:] if l.startswith('+'))+'\n'
sub('osfmk/arm/machine_routines_common.c','\tthread = current_thread();\n\n\tstate = __builtin_arm_rsr("DAIF");\n\n\tif (enable && (state & DAIF_IRQF)) {','\tthread = current_thread();\n\n'+block+'\n\tstate = __builtin_arm_rsr("DAIF");\n\n\tif (enable && (state & DAIF_IRQF)) {')
# arm_vm_init
f='osfmk/arm64/arm_vm_init.c'
sub(f,'#include <mach_kdp.h>\n#include <debug.h>\n','#include <mach_kdp.h>\n#include <linux64/linux64.h>\n#include <debug.h>\n')
sub(f,'\tset_mmu_ttb_alternate(cpu_ttep & TTBR_BADDR_MASK);\n\n\tml_enable_monitor();','''	if (linux64_hook) {
		/*
		 * LINUX64 (xnulinux): TTBR1 is Linux's. The host installs XNU's kernel L1 entries
		 * (the kernel VA range only) into Linux's top-level L1 table; TTBR0 stays Linux's.
		 */
		linux64_call(LINUX64_CALL_KERNEL_TABLES, cpu_tte);
	} else {
		set_mmu_ttb_alternate(cpu_ttep & TTBR_BADDR_MASK);
	}

	ml_enable_monitor();''')
sub(f,'\tset_mmu_ttb(invalid_ttep & TTBR_BADDR_MASK);\n\n\tflush_mmu_tlb();\n\tsweet_early_mark(10','\tif (!linux64_hook) {\n\t\tset_mmu_ttb(invalid_ttep & TTBR_BADDR_MASK);\n\t}\n\n\tflush_mmu_tlb();\n\tsweet_early_mark(10')
s=open(f).read()
if 'ARM_PTE_GP' in s: sub(f,'if (guarded) {','/* LINUX64: Linux enables SCTLR_EL1.BT1, and this kernel is not built with BTI landing pads. */\n\t\t\t\tif (guarded && !linux64_hook) {')
# 47-bit user maps serve a macOS userland: keep the stock 39-bit attributes (iOS user addresses fit them)
sub('bsd/dev/arm64/sysctl.c','int return_value = 64 - T0SZ_HW;   /* LINUX64: the user address width (pmap_user_va_bits) */','int return_value = 64 - T0SZ_BOOT;')
sub('osfmk/arm/pmap/pmap.c','#  if defined(XNU_TARGET_OS_OSX) || !__ARM_16K_PG__   /* LINUX64: macOS userland gets the whole 47-bit space by default */','#  ifdef XNU_TARGET_OS_OSX')
sub('osfmk/arm/pmap/pmap.c','#elif !__ARM_16K_PG__ && !ARM_PARAMETERIZED_PMAP\n\treturn 64 - T0SZ_HW;    /* LINUX64: user pmaps walk from level 0 (pmap_pt_attr_4k_user) */\n','')
import subprocess
subprocess.run(['git','checkout','-q','ios-base','--','osfmk/arm/pmap/pmap_pt_geometry.h'],check=True)
def plus(rej, n):
    """the added lines of hunk n of a rejected file"""
    h = open('../rej/' + rej + '.rej').read().split('\n@@')[1:][n]
    return '\n'.join(l[1:] for l in h.split('\n')[1:] if l.startswith('+')) + '\n'
# sleh.c: kernel faults, copyio recovery and user-space entry/exit while hosted, adapted to xnu-8796
f='osfmk/arm64/sleh.c'
if '#include <linux64/linux64.h>' not in open(f).read():
    sub(f,'#include <prng/entropy.h>\n','#include <linux64/linux64.h>\n#include <kern/recount.h>\n#include <prng/entropy.h>\n')
h=open('../rej/'+f+'.rej').read().split('\n@@')[-1]
blk='\n'.join(l[1:] for l in h.split('\n')[1:] if l.startswith('+'))+'\n'
def rep(old,new):
    global blk
    assert old in blk,old
    blk=blk.replace(old,new)
# 8796's find_copyio_recovery_entry takes a saved state, not a pc
rep('struct copyio_recovery_entry *e = find_copyio_recovery_entry(pc);\n','''struct copyio_recovery_entry *e = NULL;
	ptrdiff_t offset = copyio_recovery_offset(pc);
	for (struct copyio_recovery_entry *c = copyio_recover_table; c < copyio_recover_table_end; c++) {
		if (offset >= c->cre_start && offset < c->cre_end) {
			e = c;
			break;
		}
	}
''')
rep('sleh_synchronous(thread->machine.contextData, f->esr, (vm_offset_t)f->far, false);','sleh_synchronous(thread->machine.contextData, (uint32_t)f->esr, (vm_offset_t)f->far);')
open(f,'a').write(blk)
# status.c: leave SPSel as found
s=open('osfmk/arm64/status.c').read()
a=s.index('/* Sign the initial user-space thread state */'); b=s.index('ml_pac_safe_interrupts_restore(intr);',a)
seg=s[a:b].replace('"mov	x6, lr"                 "\\n"\n                        "msr	SPSel, #1"              "\\n"','"mov	x6, lr"                 "\\n"\n                        "mrs	x10, SPSel"             "\\n"\n                        "msr	SPSel, #1"              "\\n"').replace('"msr	SPSel, #0"              "\\n"','"msr	SPSel, x10"             "\\n"').replace('"x5", "x6"\n','"x5", "x6", "x10"\n')
assert seg.count('x10')==3,seg
open('osfmk/arm64/status.c','w').write(s[:a]+seg+s[b:])
# machine_routines.c
f='osfmk/arm64/machine_routines.c'
sub(f,'\t__builtin_arm_wsr("DAIFClr", (DAIFSC_IRQF | DAIFSC_FIQF));\n}\n\nvoid\nOSSynchronizeIO','''	/* LINUX64 (xnulinux): hosted, hardware IRQs stay masked; only the virtual flag changes. */
	if (linux64_hook) {
		LINUX64_VINT = 1;
		return;
	}
	__builtin_arm_wsr("DAIFClr", (DAIFSC_IRQF | DAIFSC_FIQF));
}

void
OSSynchronizeIO''')
sub(f,'ml_get_interrupts_enabled(void)\n{\n\tuint64_t        value;\n\n','ml_get_interrupts_enabled(void)\n{\n\tuint64_t        value;\n\n\t/* LINUX64: interrupts are virtual while hosted (see ml_set_interrupts_enabled_with_debug). */\n\tif (linux64_hook) {\n\t\treturn LINUX64_VINT ? TRUE : FALSE;\n\t}\n')
sub(f,'\t__builtin_arm_wsr64("TPIDRRO_EL0", 0);\n}','\tif (!linux64_hook) {\t/* LINUX64: hosted, TPIDRRO_EL0 already holds the kernel\'s thread pointer */\n\t\t__builtin_arm_wsr64("TPIDRRO_EL0", 0);\n\t}\n}')
sub(f,'\tif (cdp->cpu_set_decrementer_func) {','\t/* LINUX64 (xnulinux): the generic timer is Linux\'s; cpu_idle hands the deadline to the host. */\n\tif (linux64_hook) {\n\t\treturn;\n\t}\n\tif (cdp->cpu_set_decrementer_func) {')
# stack.c: 32 KiB aligned stacks while hosted (8796 has one guard page below)
f='osfmk/kern/stack.c'
sub(f,'return linux64_hook ? ptoa(1) + 0x8000 : ptoa(2);','return linux64_hook ? ptoa(1) + 0x8000 : ptoa(1);')
sub(f,'\t\t    kernel_stack_size + ptoa(2), stack_addr_mask,\n','\t\t    kernel_stack_size + linux64_stack_lead() + ptoa(1), linux64_stack_mask(),\n')
sub(f,'\t\tstack += PAGE_SIZE;\n','''		stack += linux64_stack_lead();
		if (linux64_hook && (stack & 0x7fff)) {	/* Linux would take an exception on it for a stack overflow */
			panic("linux64: kernel stack %p is not on a 32 KiB boundary", (void *)stack);
		}
''')
sub(f,'\t\t\tstack -= PAGE_SIZE;\n\t\t\tkmem_free(kernel_map, stack, kernel_stack_size + ptoa(2));','\t\t\tstack -= linux64_stack_lead();\n\t\t\tkmem_free(kernel_map, stack, kernel_stack_size + linux64_stack_lead() + ptoa(1));')
# sched_prim.c
f='osfmk/kern/sched_prim.c'
if '#include <linux64/linux64.h>' not in open(f).read():
    sub(f,'#include <kern/sched_prim.h>\n','#include <kern/sched_prim.h>\n#include <linux64/linux64.h>\n')
s=open(f).read()
a=s.index('\trecount_processor_idle(&processor->pr_recount, &snap);'); b=s.index('while (1) {\n',a)+len('while (1) {\n')
open(f,'w').write(s[:b]+"\t\tlinux64_count(LINUX64_CTR_IDLE_THREAD);\t/* LINUX64: for the host's monitor */\n"+s[b:])
open(f,'a').write(plus(f, len(open('../rej/'+f+'.rej').read().split('\n@@'))-2))

# ---- prng: the host's generator until corecrypto registers
def include(f, anchor):
    if '#include <linux64/linux64.h>' not in open(f).read():
        sub(f, anchor, '#include <linux64/linux64.h>\n' + anchor)
f='osfmk/prng/prng_random.c'
include(f,'#include <kern/locks.h>\n')
sub(f,'\tprng_funcs.initgen(prng_ctx, cpu);','\tif (prng_funcs.initgen != NULL) {\n\t\tprng_funcs.initgen(prng_ctx, cpu);\n\t}')
sub(f,'\tprng_funcs.refresh(prng_ctx);\n\tread_random_generate(buffer, numbytes);','''	/* LINUX64: hosted without the corecrypto kext prng_funcs stays zeroed; the host's generator stands in. */
	if (prng_funcs.generate == NULL && linux64_hook) {
		linux64_random(buffer, numbytes);
		return;
	}
	prng_funcs.refresh(prng_ctx);
	read_random_generate(buffer, numbytes);''')
sub(f,'\tprng_funcs.reseed(prng_ctx, sizeof(seed), seed);\n\tcc_clear(sizeof(seed), seed);\n\n\treturn 0;','\tif (prng_funcs.reseed != NULL) {\n\t\tprng_funcs.reseed(prng_ctx, sizeof(seed), seed);\n\t}\n\tcc_clear(sizeof(seed), seed);\n\n\treturn 0;')
# ---- cpu.c: idle and CPU start go to the host
f='osfmk/arm64/cpu.c'
sub(f,'\tbool idle_disallowed = false;\n\n\tif (__improbable((!idle_enable))) {','\tbool idle_disallowed = false;\n\n\tif (linux64_hook) {\n\t\tlinux64_cpu_idle(cpu_data_ptr);\n\t}\n\tif (__improbable((!idle_enable))) {')
sub(f,'\t\t(void) PE_cpu_start(cpu_data_ptr->cpu_id, (vm_offset_t)NULL, (vm_offset_t)NULL);\n','\t\tif (linux64_hook) {\n\t\t\t/* LINUX64: the host starts the CPU, on a Linux CPU of that MPIDR, at linux64_cpu_entry */\n\t\t\tlinux64_call2(LINUX64_CALL_CPU_START, cpu_data_ptr->cpu_phys_id, (unsigned long)cpu_data_ptr);\n\t\t} else {\n\t\t\t(void) PE_cpu_start(cpu_data_ptr->cpu_id, (vm_offset_t)NULL, (vm_offset_t)NULL);\n\t\t}\n')
# ---- console, panic, backtrace, assert, spin waits, signing macro, kprintf include
include('osfmk/console/serial_console.c','#include <')
sub('osfmk/console/serial_console.c','\tassert(str != NULL);\n','''	assert(str != NULL);

	/* LINUX64: hosted XNU's console (/dev/console, km) goes to the host. */
	if (linux64_hook && size > 0) {
		linux64_call2(LINUX64_CALL_CONSOLE_WRITE, (unsigned long)str, (unsigned long)size);
		return;
	}
''')
f='osfmk/kern/debug.c'
include(f,'#include <kern/')
hs=open('../rej/'+f+'.rej').read().split('\n@@')[1:]
body=plus(f,[i for i,h in enumerate(hs) if 'LINUX64_CALL_PANIC' in h][0])
sub(f,'#pragma clang diagnostic pop\n\n#if defined(SWEET)\n','#pragma clang diagnostic pop\n\n'+body+'\n#if defined(SWEET)\n')
f='osfmk/kern/backtrace.c'
s=open(f).read(); a=s.index('#if __x86_64__\nstatic void\n_backtrace_packed_out_of_reach')
open(f,'w').write(s[:a]+s[a:].replace('#if __x86_64__\n','#if __x86_64__ || __arm64__\t/* LINUX64: hosted, a kernel stack also has frames in Linux\'s text */\n',1))
sub('osfmk/kern/assert.h','#define assert(ex)  \\\n\t(__builtin_expect(!!((ex)), 1L) ? (void)0 : Assert(__FILE_NAME__, __LINE__, # ex))\n',r'''#if defined(XNU_KERNEL_PRIVATE) && defined(__arm64__)
/* LINUX64: hosted there is no XNU exception vector for the assert trap: report a failed assert() to the host. */
#ifdef __cplusplus
extern "C" {
#endif
extern unsigned long linux64_hook;
extern void linux64_assert_report(const char *file, int line, const char *expr);
#ifdef __cplusplus
}
#endif
#define assert(ex)  \
	(__builtin_expect(!!((ex)), 1L) ? (void)0 : linux64_hook ? linux64_assert_report(__FILE_NAME__, __LINE__, # ex) \
	: Assert(__FILE_NAME__, __LINE__, # ex))
#else
#define assert(ex)  \
	(__builtin_expect(!!((ex)), 1L) ? (void)0 : Assert(__FILE_NAME__, __LINE__, # ex))
#endif
''')
sub('osfmk/arm/locks.h','#define wait_for_event()        __builtin_arm_wfe()','''/* LINUX64: hosted, a waiting CPU lets the host take its interrupts every ~1 ms (linux64_spin_relax) */
extern unsigned long linux64_hook;
extern void linux64_spin_relax(void);
#define wait_for_event()        ({ __builtin_arm_wfe(); if (__improbable(linux64_hook)) linux64_spin_relax(); })''')
f='osfmk/mach/arm/thread_status.h'
s=open(f).read(); a=s.index('define MANIPULATE_SIGNED_THREAD_STATE'); b=s.index('while (0)',a); m=s[a:b]
if 'mrs	x10, SPSel' not in m:
    m=m.replace('"msr	SPSel, #1"','"mrs	x10, SPSel"			"\\n"            \\\n\t                "msr	SPSel, #1"',1)
m=m.replace('"msr	SPSel, #0"','"msr	SPSel, x10"')
m,n=re.subn(r'("x9")(\s*\\\n\s*\);)',r'\1, "x10"\2',m); assert n==1
assert 'SPSel, x10' in m
open(f,'w').write(s[:a]+m+s[b:])
include('pexpert/arm/pe_kprintf.c','#include <')
# ---- assembly: TPIDR_EL1 is Linux's; XNU's kernel thread pointer lives in TPIDRRO_EL0
for f in ('osfmk/arm64/locore.s','osfmk/arm64/cswitch.s','osfmk/arm64/exception_asm.h','osfmk/arm64/asm.h','osfmk/arm64/machine_routines_asm.s','osfmk/arm64/pac_asm.h'):
    s=open(f).read().replace('TPIDR_EL1','TPIDRRO_EL0'); open(f,'w').write(s)
# the context switch must no longer put the user's TSD into TPIDRRO_EL0 (linux64_el0_run does on return to user space)
sub('osfmk/arm64/cswitch.s','\tldr\t\t$1, [$0, TH_CTH_SELF]\t\t\t\t// Get cthread pointer\n\tmsr\t\tTPIDRRO_EL0, $1\n','')
f='osfmk/arm64/locore.s'
hosted='''	// LINUX64: hosted, the return to user space goes through C (linux64_el0_run)
	adrp	x9, _linux64_hook@PAGE
	ldr		x9, [x9, _linux64_hook@PAGEOFF]
	cbz		x9, 1f
	b		EXT(linux64_thread_bootstrap_return)
1:
'''
for lab in ('LEXT(thread_bootstrap_return)\n','LEXT(arm64_thread_exception_return)\n'):
    s=open(f).read(); assert s.count(lab)==1
    open(f,'w').write(s.replace(lab,lab+hosted))
sub('osfmk/arm64/machine_routines_asm.s','// Restore interrupt state\n\tPOP_FRAME\n\tARM64_STACK_EPILOG\n','// Restore interrupt state\nLreplace_bootstack_hosted:\n\tPOP_FRAME\n\tARM64_STACK_EPILOG\n')
