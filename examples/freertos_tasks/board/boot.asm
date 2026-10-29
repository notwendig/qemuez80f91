    XDEF _trap
    XDEF _startup_snapshot
    XREF _startup_ports
    XREF _startup_sp
    SEGMENT CODE
    .ASSUME ADL=1
_trap:
    di
    halt
    jr _trap
_startup_snapshot:
    ld (_startup_sp),sp
    in0 a,(05Ch)
    ld (_startup_ports+0),a
    in0 a,(05Dh)
    ld (_startup_ports+1),a
    in0 a,(05Eh)
    ld (_startup_ports+2),a
    in0 a,(05Fh)
    ld (_startup_ports+3),a
    in0 a,(0A8h)
    ld (_startup_ports+4),a
    in0 a,(0A9h)
    ld (_startup_ports+5),a
    in0 a,(0AAh)
    ld (_startup_ports+6),a
    in0 a,(0ABh)
    ld (_startup_ports+7),a
    in0 a,(0ACh)
    ld (_startup_ports+8),a
    in0 a,(0ADh)
    ld (_startup_ports+9),a
    in0 a,(0AEh)
    ld (_startup_ports+10),a
    in0 a,(0AFh)
    ld (_startup_ports+11),a
    in0 a,(0B0h)
    ld (_startup_ports+12),a
    in0 a,(0B1h)
    ld (_startup_ports+13),a
    in0 a,(0B2h)
    ld (_startup_ports+14),a
    in0 a,(0B3h)
    ld (_startup_ports+15),a
    in0 a,(0B4h)
    ld (_startup_ports+16),a
    in0 a,(0B5h)
    ld (_startup_ports+17),a
    in0 a,(0F0h)
    ld (_startup_ports+18),a
    in0 a,(0F1h)
    ld (_startup_ports+19),a
    in0 a,(0F2h)
    ld (_startup_ports+20),a
    in0 a,(0F3h)
    ld (_startup_ports+21),a
    in0 a,(0F7h)
    ld (_startup_ports+22),a
    in0 a,(0F8h)
    ld (_startup_ports+23),a
    ret
    END
