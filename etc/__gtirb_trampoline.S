#===================================
.intel_syntax noprefix
#===================================

nop
nop
nop
nop
nop
nop
nop
nop

#===================================
.text
.align 16
#===================================


# BEGIN - Function Header
#-----------------------------------
.align 2
.globl __gtirb_trampoline
.type __gtirb_trampoline, @function
__gtirb_trampoline:
#-----------------------------------
# END   - Function Header

__gtirb_trampoline:

            push RBP
            mov RBP,RSP
            mov EDI,OFFSET .L_400628
            mov EAX,0
            call printf@PLT
            mov EDI,-1
            call exit@PLT

            nop



#===================================
.section .rodata
.align 16
#===================================

.L_400628:
          .string "GTIRB block reduce trampoline called. This was a block that was removed, exiting..\n"
