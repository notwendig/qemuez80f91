#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H
#define configUSE_PREEMPTION 1
#define configUSE_TIME_SLICING 1
#define configCPU_CLOCK_HZ 50000000UL
#define configTICK_RATE_HZ 1000UL
#define configMAX_PRIORITIES 3
#define configMINIMAL_STACK_SIZE 256
#define configMAX_TASK_NAME_LEN 8
#define configUSE_16_BIT_TICKS 1
#define configIDLE_SHOULD_YIELD 1
#define configSUPPORT_STATIC_ALLOCATION 1
#define configSUPPORT_DYNAMIC_ALLOCATION 0
#define configUSE_IDLE_HOOK 1
#define configUSE_TICK_HOOK 0
#define configUSE_TIMERS 0
#define configCHECK_FOR_STACK_OVERFLOW 0
#define configSTACK_DEPTH_TYPE uint24_t
#define INCLUDE_vTaskDelay 1
void vAssertCalled(int x, const char *file, int line);
#define configASSERT(x) vAssertCalled((int)(x), __FILE__, __LINE__)
#endif
