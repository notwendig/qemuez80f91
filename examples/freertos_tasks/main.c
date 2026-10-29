#include "FreeRTOS.h"
#include "task.h"
#include <eZ80F91.h>

volatile uint8_t criticalcounter;
volatile unsigned runs[2];
volatile unsigned failure;
StaticTask_t tcbs[3];
StackType_t stacks[3][512];
extern void firstTASK(void);
void EnterCritical(void) { DI(); ++criticalcounter; }
void ExitCritical(void) { if(criticalcounter && !--criticalcounter) EI(); }
void vAssertCalled(int x, const char *file, int line) {
    if(!x) { DI(); failure = line; asm("halt"); }
}
static void preTask(void) { EI(); }
StackType_t *pxPortInitialiseStack(StackType_t *top, StackType_t *end,
                                 TaskFunction_t code, void *arg) {
    *--top = (StackType_t)arg;
    *--top = 0;
    *--top = (StackType_t)code;
    *--top = (StackType_t)preTask;
    *--top = 0;
    return top;
}
BaseType_t xPortStartScheduler(void) {
    DI();
    TMR0_IER = 0;
    _set_vector(0x54, vPortYieldFromTick);
    TMR0_RR_H = 12; TMR0_RR_L = 53;
    TMR0_CTL = 0x8f; TMR0_IER = 1;
    firstTASK();
    return 0;
}
void vPortEndScheduler(void) { DI(); asm("halt"); }
void vApplicationGetIdleTaskMemory(StaticTask_t **tcb, StackType_t **stack,
                                  uint32_t *size) {
    *tcb = &tcbs[2]; *stack = stacks[2]; *size = 512;
}
static void worker(void *arg) {
    unsigned id = (unsigned)arg;
    unsigned local = 0;
    for(;;) {
        ++local;
        runs[id] = local;
        UART0_THR = 'A' + id;
        if(runs[0] >= 4 && runs[1] >= 4) {
            DI(); TMR0_CTL = 0; UART0_THR = '!';
            asm("halt");
        }
        /* Busy wait: only timer preemption lets the other task run. */
        { TickType_t start = xTaskGetTickCount();
          while(xTaskGetTickCount() == start) {} }
    }
}
void main(void) {
    xTaskCreateStatic(worker,"A",512,(void*)0,1,stacks[0],&tcbs[0]);
    xTaskCreateStatic(worker,"B",512,(void*)1,1,stacks[1],&tcbs[1]);
    stacks[0][0] = 0x123456;
    stacks[1][0] = 0xabcdef;
    vTaskStartScheduler();
    failure = 0xffffff; asm("halt");
}
