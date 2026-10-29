#include <eZ80F91.h>
volatile unsigned char bss_probe[8];
volatile unsigned data_probe = 0x123456;
volatile unsigned result;
int main(void)
{
    unsigned i;
    result = data_probe;
    for (i=0; i<sizeof(bss_probe); i++)
        result += bss_probe[i];
    PD_DDR=0xff;
    PD_ALT1=0;
    PD_ALT2=3;
    UART0_LCTL=3;
    while (!(UART0_LSR & 0x20)) { }
    UART0_THR='C';
    asm(" halt");
    return 0;
}
