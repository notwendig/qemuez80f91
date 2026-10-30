#include "FreeRTOS.h"
#include "task.h"
#include <eZ80F91.h>

volatile uint8_t criticalcounter;
volatile unsigned runs[2];
volatile unsigned event_count;
volatile uint8_t events[10];
volatile TickType_t event_ticks[10];
volatile uint8_t idle_seen[8];
volatile unsigned idle_entries;
volatile unsigned cooperative_done;
volatile unsigned done;
volatile TickType_t final_tick;
extern unsigned interrupts_enabled(void);
volatile unsigned failure;
StaticTask_t tcbs[3];
StackType_t stacks[3][512];
extern void firstTASK(void);
void EnterCritical(void) { DI(); ++criticalcounter; }
void ExitCritical(void) { if(criticalcounter && !--criticalcounter) EI(); }
void vAssertCalled(int x, const char *file, int line) {
    if(!x) { DI(); TMR0_CTL = 0; failure = line; asm("halt"); }
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
    /* First prove voluntary switching with no possible timer interrupt. */
    TMR0_CTL = 0; TMR0_IER = 1;
    firstTASK();
    return 0;
}
void vPortEndScheduler(void) { DI(); asm("halt"); }
void vApplicationGetIdleTaskMemory(StaticTask_t **tcb, StackType_t **stack,
                                  configSTACK_DEPTH_TYPE *size) {
    *tcb = &tcbs[2]; *stack = stacks[2]; *size = 512;
}
static void event(uint8_t c) {
    unsigned n = event_count;
    configASSERT(n < 10);
    events[n] = c;
    event_ticks[n] = xTaskGetTickCount();
    event_count = n + 1;
    UART0_THR = c;
}
static void check_tick(unsigned offset) {
    configASSERT(xTaskGetTickCount() ==
                 (TickType_t)(configINITIAL_TICK_COUNT + offset));
}
void vApplicationIdleHook(void) {
    unsigned elapsed = xTaskGetTickCount() - (TickType_t)configINITIAL_TICK_COUNT;
    ++idle_entries;
    if(elapsed < 8) idle_seen[elapsed] = 1;
}
static void worker_a(void *arg) {
    volatile unsigned canary = 0x123456;
    ++runs[0];
    configASSERT(interrupts_enabled());
    event('A');
    EnterCritical();
    taskYIELD();
    configASSERT(criticalcounter == 1 && !interrupts_enabled());
    configASSERT(canary == 0x123456);
    ExitCritical();
    configASSERT(interrupts_enabled());
    event('a');
    taskYIELD();
    configASSERT(cooperative_done && interrupts_enabled());
    check_tick(0);
    vTaskDelay(5);
    ++runs[0];
    configASSERT(canary == 0x123456 && interrupts_enabled());
    check_tick(5);
    event('5');
    vTaskDelay(10);
    configASSERT(0);
}
static void worker_b(void *arg) {
    volatile unsigned canary = 0xabcdef;
    ++runs[1];
    event('B');
    EnterCritical();
    EnterCritical();
    taskYIELD();
    configASSERT(criticalcounter == 2 && !interrupts_enabled());
    configASSERT(canary == 0xabcdef);
    ExitCritical();
    configASSERT(criticalcounter == 1 && !interrupts_enabled());
    ExitCritical();
    configASSERT(criticalcounter == 0 && interrupts_enabled());
    event('b');
    taskYIELD();
    configASSERT(canary == 0xabcdef && interrupts_enabled());
    check_tick(0);
    cooperative_done = 1;
    event('D');
    TMR0_CTL = 0x8f;
    vTaskDelay(2);
    ++runs[1];
    check_tick(2);
    event('2');
    vTaskDelay(2);
    ++runs[1];
    check_tick(4);
    event('4');
    vTaskDelay(2);
    ++runs[1];
    check_tick(6);
    configASSERT(canary == 0xabcdef && interrupts_enabled());
    configASSERT(runs[0] == 2 && runs[1] == 4);
    event('6');
    DI();
    TMR0_CTL = 0;
    final_tick = xTaskGetTickCount();
    done = 1;
    event('!');
    DI();
    asm("halt");
    for(;;) {}
}
void main(void) {
    xTaskCreateStatic(worker_a,"A",512,(void*)0,1,stacks[0],&tcbs[0]);
    xTaskCreateStatic(worker_b,"B",512,(void*)1,1,stacks[1],&tcbs[1]);
    stacks[0][0] = 0x123456;
    stacks[1][0] = 0xabcdef;
    stacks[2][0] = 0x654321;
    vTaskStartScheduler();
    failure = 0xffffff; asm("halt");
}
