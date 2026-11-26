/* rebootto REASON: restart with a reason string ("bootloader"), which busybox reboot cannot pass. */
#include <linux/reboot.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	sync();
	syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, argc > 1 ? argv[1] : "bootloader");
	perror("reboot");
	return 1;
}
