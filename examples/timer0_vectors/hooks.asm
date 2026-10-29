    XREF __init_default_vectors
    XREF _set_vector
    XDEF __init
    XDEF _trap
    XDEF switch
    XDEF _ticks
    XDEF _done
    SEGMENT CODE
    .ASSUME ADL=1
__init:
    di
    ld sp,0B90000h
    xor a
    ld (_ticks),a
    call __init_default_vectors
    ld hl,timer_isr
    push hl
    ld hl,054h
    push hl
    call _set_vector
    pop bc
    pop bc
    ld a,0FFh
    out0 (0A3h),a
    xor a
    out0 (0A4h),a
    ld a,3
    out0 (0A5h),a
    out0 (0C3h),a
    ld a,0Ch
    out0 (064h),a
    ld a,035h
    out0 (063h),a
    ld a,1
    out0 (061h),a
    ld a,08Fh
    out0 (060h),a
    ld bc,0123456h
    ld de,0345678h
    ld hl,056789Ah
    ld ix,0789ABCh
    ld iy,09ABCDEh
    ei
wait_tick:
    halt
    ld a,(_ticks)
    cp 3
    jr nz,wait_tick
    di
    xor a
    out0 (060h),a
_done:
    halt
    jr _done
timer_isr:
    in0 a,(062h)
    ld a,(_ticks)
    inc a
    ld (_ticks),a
    ld a,'T'
    out0 (0C0h),a
    ret
switch:
    ret
_trap:
    di
    halt
    jr _trap
    SEGMENT BSS
_ticks:
    ds 1
    END
