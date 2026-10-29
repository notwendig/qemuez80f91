; Equivalent eZ80F91 assembly; the raw ROM is built by make_hello_uart0.py.
; UART baud timing is not yet simulated by the emulator.
    .assume ADL=0
    org 0
    jp.lil start
    .assume ADL=1
start:
    di
    ld sp,0FFFFF0h
    ld a,0FFh
    out0 (0A3h),a       ; PD_DDR: alternate function requires DDR=1
    xor a
    out0 (0A4h),a       ; PD_ALT1=0
    ld a,3
    out0 (0A5h),a       ; PD_ALT2: UART0 TX/RX enabled
    ld a,083h
    out0 (0C3h),a       ; DLAB=1
    ld a,2
    out0 (0C0h),a       ; divisor low
    xor a
    out0 (0C1h),a       ; divisor high
    ld a,3
    out0 (0C3h),a       ; DLAB=0, 8N1
    xor a
    out0 (0C1h),a       ; interrupts disabled
    out0 (0C2h),a       ; FIFO disabled
    ld hl,message
    call puts
    halt
puts:
    ld a,(hl)
    or a
    jr z,done
    push hl
    call putc
    pop hl
    inc hl
    jr puts
done:
    ret
putc:
    push af
wait_tx:
    in0 a,(0C5h)
    and 020h
    jr z,wait_tx
    pop af
    out0 (0C0h),a
    ret
message:
    db "Hello eZ80F91",13,10,0
