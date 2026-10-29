    XDEF init_bsp
    XDEF putc
    XDEF getc
    XDEF kbhit
    SEGMENT CODE
    .ASSUME ADL=1
init_bsp:
    di
    ld a,0ffh
    out0 (0a3h),a
    xor a
    out0 (0a4h),a
    out0 (0c1h),a
    out0 (0c2h),a
    ld a,3
    out0 (0a5h),a
    ld a,080h
    out0 (0c3h),a
    ld a,27
    out0 (0c0h),a
    xor a
    out0 (0c1h),a
    ld a,3
    out0 (0c3h),a
    ret
putc:
    push bc
    ld b,a
wait_tx:
    in0 a,(0c5h)
    and 020h
    jr z,wait_tx
    ld a,b
    out0 (0c0h),a
    ld a,1
    or a
    pop bc
    ret
kbhit:
    in0 a,(0c5h)
    and 1
    ret
getc:
    call kbhit
    jr z,getc
    in0 a,(0c0h)
    ret
    END
