    XREF __c_startup
    XREF _main
    DEFINE .RESET, SPACE=ROM
    SEGMENT .RESET
    .ASSUME ADL=0
    jp.lil start
    .ASSUME ADL=1
start:
    di
    ld sp,0B90000h
    ld hl,0BBBBBBh
    ld (06B000h),hl
    ld hl,06B003h
    ld bc,64
fill:
    ld (hl),0A5h
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,fill
    call __c_startup
    call _main
    halt
    END
