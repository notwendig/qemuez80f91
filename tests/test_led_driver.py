#!/usr/bin/env python3
"""Exercise the real firmware LED C driver with deterministic ISR interleaving."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DRIVER=ROOT/'subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG'
with tempfile.TemporaryDirectory(prefix='led-driver-') as temp:
    work=Path(temp)
    shutil.copyfile(DRIVER/'inc/ez80_leds.h',work/'ez80_leds.h')
    (work/'FreeRTOS.h').write_text('''#pragma once
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
typedef int BaseType_t;
typedef unsigned UBaseType_t;
typedef uint32_t TickType_t;
typedef unsigned char CHAR;
typedef unsigned char UCHAR;
typedef uint8_t UINT8;
typedef uint16_t UINT16;
typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
extern unsigned criticalDepth;
extern TickType_t fakeTick;
#define portENTER_CRITICAL() (++criticalDepth)
#define portEXIT_CRITICAL() (assert(criticalDepth),--criticalDepth)
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define configCPU_CLOCK_HZ 50000000UL
#define configTICK_RATE_HZ 1000
#define configLED5x7TICK_RATE_HZ 300
#define configMINIMAL_STACK_SIZE 512
#define LED5x7_CDELAY 300
#define LED5x7_SHIFTT 60
#define LED5x7_QUEUES 80
#define LED5x7_PRIO 7
#define eIncrement 1
''')
    (work/'task.h').write_text('''#pragma once
#include "FreeRTOS.h"
TickType_t ulTaskNotifyTake(BaseType_t clear, TickType_t timeout);
static inline TickType_t xTaskGetTickCount(void) {return fakeTick;}
static inline TickType_t xTaskGetTickCountFromISR(void) {return fakeTick;}
static inline void vTaskDelay(TickType_t n) {fakeTick+=n;}
static inline void xTaskNotifyIndexedFromISR(void *h,unsigned index,unsigned value,int action,void *wake) {assert(!criticalDepth);}
static inline int xTaskCreate(void (*fn)(void*),const char *name,unsigned stack,void *arg,unsigned prio,void **handle) {*handle=(void*)1;return 1;}
''')
    (work/'queue.h').write_text('''#pragma once
#include "FreeRTOS.h"
static inline void *xQueueCreate(unsigned n,unsigned size) {return (void*)1;}
static inline int xQueueReceive(void *q,void *p,TickType_t timeout) {*(CHAR*)p=' ';return 1;}
static inline int xQueueSend(void *q,const void *p,TickType_t timeout) {return 1;}
static inline unsigned uxQueueSpacesAvailable(void *q) {return 80;}
static inline unsigned uxQueueMessagesWaiting(void *q) {return 0;}
''')
    (work/'eZ80F91.h').write_text('''#pragma once
#include <stdint.h>
extern uint8_t TMR1_IIR,TMR1_IER,TMR1_DR_H,TMR1_DR_L,TMR1_RR_H,TMR1_RR_L,TMR1_CTL;
#define TIMER1_IVECT 0
static inline void _set_vector(unsigned n,void (*fn)(void)) {}
''')
    (work/'String.h').write_text('#include <string.h>\n')
    harness='''#include <stdio.h>
#include <string.h>
#include "FreeRTOS.h"
unsigned criticalDepth;
TickType_t fakeTick;
uint8_t TMR1_IIR,TMR1_IER,TMR1_DR_H,TMR1_DR_L,TMR1_RR_H,TMR1_RR_L,TMR1_CTL;
static uint8_t anode,cathode;
#define LEDMATRIX_ANODE anode
#define LEDMATRIX_CATHODE cathode
#include DRIVER_SOURCE
static const uint8_t oldImage[7]={0xfe,0xfd,0xfb,0xf7,0xef,0xff,0xff};
static const uint8_t newImage[7]={0xe0,0xe1,0xe2,0xe3,0xe4,0xe5,0xe6};
static unsigned waits,oldSeen;
static void scan(uint8_t *out) {
    for(unsigned r=0;r<7;r++) {
        LED5x7Tick();assert(anode==(0x80|(1<<r)));out[r]=cathode;
    }
}
TickType_t ulTaskNotifyTake(BaseType_t clear,TickType_t timeout) {
    uint8_t frame[7];assert(!criticalDepth);scan(frame);waits++;
    if(!memcmp(frame,oldImage,7)) oldSeen++;
    return 1;
}
void shiftDisplay(void) {} /* Actual assembly is separately tested in QEMU. */
static void prepare(const uint8_t *image) {for(unsigned r=0;r<7;r++) dply[r]=0xff00|image[r];}
static void resetDriver(void) {fakeTick=0;initLED5x7();assert(!criticalDepth);}
int main(void) {
    uint8_t got[7],blank[7];memset(blank,255,7);
    resetDriver();prepare(oldImage);publishDisplay();
    for(unsigned n=0;n<6;n++){scan(got);assert(!memcmp(got,blank,7));}
    scan(got);assert(!memcmp(got,oldImage,7));
    LED5x7_set(0,0);LED5x7_set(4,6);
    LED5x7Tick();assert(cathode==(oldImage[0]&~16));
    LED5x7_clr(0,0);LED5x7_clr(4,6);
    for(unsigned r=1;r<7;r++){LED5x7Tick();assert(cathode==(r==6?0xfe:oldImage[r]));}
    scan(got);assert(!memcmp(got,oldImage,7));
    LED5x7_set(4,0);LED5x7_clr(4,0);scan(got);assert(got[0]==oldImage[0]);
    LED5x7_set(5,0);LED5x7_set(0,7);LED5x7_clr(255,255);
    scan(got);assert(!memcmp(got,oldImage,7));
    /* Interrupt the seven-row work update after every individual store. */
    for(unsigned r=0;r<7;r++) {dply[r]=0xff00|newImage[r];LED5x7Tick();assert(cathode==oldImage[r]);}
    publishDisplay();
    for(unsigned n=0;n<8;n++){scan(got);assert(!memcmp(got,oldImage,7)||!memcmp(got,newImage,7));}
    assert(!memcmp(got,newImage,7));
    /* Producer backpressure must preserve the pending old frame. */
    resetDriver();prepare(oldImage);publishDisplay();prepare(newImage);publishDisplay();
    assert(waits && oldSeen);
    for(unsigned n=0;n<8;n++) scan(got);
    assert(!memcmp(got,newImage,7));
    /* Elapsed time never commits a frame before the seventh scan. */
    resetDriver();prepare(oldImage);publishDisplay();scan(got);assert(!memcmp(got,blank,7));
    fakeTick=30000;scan(got);assert(!memcmp(got,blank,7));
    for(unsigned n=0;n<4;n++) scan(got);
    assert(!memcmp(got,blank,7));
    scan(got);assert(!memcmp(got,oldImage,7));
    assert(!criticalDepth);
    puts("PASS: real LED driver: complete-frame publication, ISR interleaving, 7-scan commit without timeout, pending-frame backpressure, static OR set/clear and scan-boundary overlay");
    return 0;
}
'''
    (work/'test.c').write_text(harness.replace('DRIVER_SOURCE','"'+str(DRIVER/'src/ez80_leds.c')+'"'))
    subprocess.run(['cc','-std=c11','-O2','-g','-D_FORTIFY_SOURCE=3',
                    '-I',str(work),str(work/'test.c'),'-o',str(work/'test')],check=True)
    subprocess.run([str(work/'test')],check=True)
