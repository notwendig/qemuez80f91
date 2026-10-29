    XREF __c_startup
    XREF __init_default_vectors
    XREF _main
    XDEF __init
    XDEF _trap
    SEGMENT CODE
    .ASSUME ADL=1
__init:
    di
    ld sp,0B90000h
    call __c_startup
    call __init_default_vectors
    ld a,0FFh
    out0 (0A3h),a
    xor a
    out0 (0A4h),a
    ld a,3
    out0 (0A5h),a
    out0 (0C3h),a
    call _main
_trap:
    di
    halt
    jr _trap
    XDEF _interrupts_enabled
_interrupts_enabled:
    ld hl,0
    ld a,i
    ret po
    inc hl
    ret
    END
