/* Development-board controller only. MuJoCo is the plant; no actuator pins. */
#include "../protocol/replay.h"
#include "build_identity.h"
#include "stm32h7xx_hal.h"
#include <errno.h>
#include <string.h>

UART_HandleTypeDef uart;
DMA_HandleTypeDef rx_dma;
TIM_HandleTypeDef timer;
static VvDevice device;
static VvReplay replay;
volatile uint32_t board_error, timer_ticks, last_timer_entry;
static volatile uint32_t rx_produced, rx_consumed, uart_error;
static uint32_t rx_last_position;
static uint8_t rx_bytes[512] __attribute__((section(".dma"), aligned(32)));

/* Full decoded inputs; timing telemetry stays in DTCM. */
CtrlSensors replay_inputs[VV_TICKS] __attribute__((section(".replay_inputs"), used, aligned(32)));
VvTelemetry replay_telemetry __attribute__((section(".telemetry"), used, aligned(8)));
VvTiming replay_timing __attribute__((section(".replay_timing"), used, aligned(8)));
extern uint8_t _stack_limit, _flash_image_end;
static uint32_t stack_painted, flash_crc, flash_bytes;
static volatile uint32_t timed_window;

static void paint_stack(void) {
    __disable_irq();
    volatile uint8_t *p = &_stack_limit;
    uintptr_t stop = __get_MSP() - 256u; /* Never overwrite active frames. */
    stack_painted = (uint32_t)(stop - (uintptr_t)p);
    while ((uintptr_t)p < stop)
        *p++ = 0xa5;
    __enable_irq();
}
static void diagnostics(void) {
    uint32_t free = 0;
    volatile const uint8_t *p = &_stack_limit;
    while (free < stack_painted && p[free] == 0xa5)
        free++;
    replay.stack_free = free;
    replay.stack_painted = stack_painted;
    replay.fpscr = __get_FPSCR();
    replay.flash_crc = flash_crc;
    replay.flash_bytes = flash_bytes;
}

static void fatal(uint32_t reason) {
    board_error = reason;
    __disable_irq();
    for (;;)
        __WFI();
}
static void check(HAL_StatusTypeDef status, uint32_t reason) {
    if (status != HAL_OK)
        fatal(reason);
}
static void assert_dispatch_mode(uint32_t timed) {
    /* Register readback, not just a software mode flag: exactly one dispatcher. */
    if (timed_window != timed || !!NVIC_GetEnableIRQ(TIM6_DAC_IRQn) != timed ||
        !!(TIM6->DIER & TIM_DIER_UIE) != timed || !!NVIC_GetEnableIRQ(USART3_IRQn) != !timed ||
        !!NVIC_GetEnableIRQ(DMA1_Stream0_IRQn) != !timed)
        fatal(27);
}

static void clock_init(void) {
    /* ST NUCLEO-H723ZG example: 8 MHz ST-LINK MCO, PLL 4/260/1, 520 MHz. */
    check(HAL_PWREx_ConfigSupply(PWR_LDO_SUPPLY), 1);
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE0);
    uint32_t start = HAL_GetTick();
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {
        if (HAL_GetTick() - start > 100)
            fatal(2);
    }
    RCC_OscInitTypeDef osc = {0};
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_BYPASS;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 4;
    osc.PLL.PLLN = 260;
    osc.PLL.PLLP = 1;
    osc.PLL.PLLQ = 4;
    osc.PLL.PLLR = 2;
    osc.PLL.PLLRGE = RCC_PLL1VCIRANGE_1;
    osc.PLL.PLLVCOSEL = RCC_PLL1VCOWIDE;
    osc.PLL.PLLFRACN = 0;
    check(HAL_RCC_OscConfig(&osc), 3);
    RCC_ClkInitTypeDef clocks = {0};
    clocks.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_D1PCLK1 |
                       RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2 | RCC_CLOCKTYPE_D3PCLK1;
    clocks.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clocks.SYSCLKDivider = RCC_SYSCLK_DIV1;
    clocks.AHBCLKDivider = RCC_HCLK_DIV2;
    clocks.APB3CLKDivider = RCC_APB3_DIV2;
    clocks.APB1CLKDivider = RCC_APB1_DIV2;
    clocks.APB2CLKDivider = RCC_APB2_DIV2;
    clocks.APB4CLKDivider = RCC_APB4_DIV2;
    check(HAL_RCC_ClockConfig(&clocks, FLASH_LATENCY_3), 4);
    SystemCoreClockUpdate();
    if (SystemCoreClock != 520000000u || HAL_RCC_GetPCLK1Freq() != 130000000u)
        fatal(5);
}

static void uart_init(void) {
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();
    __HAL_RCC_D2SRAM1_CLK_ENABLE();
    __HAL_RCC_D2SRAM2_CLK_ENABLE();
    __HAL_RCC_USART3_CLK_ENABLE();
    RCC_PeriphCLKInitTypeDef peripheral = {0};
    peripheral.PeriphClockSelection = RCC_PERIPHCLK_USART3;
    peripheral.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_D2PCLK1;
    check(HAL_RCCEx_PeriphCLKConfig(&peripheral), 6);
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART3;
    HAL_GPIO_Init(GPIOD, &gpio);
    rx_dma.Instance = DMA1_Stream0;
    rx_dma.Init.Request = DMA_REQUEST_USART3_RX;
    rx_dma.Init.Direction = DMA_PERIPH_TO_MEMORY;
    rx_dma.Init.PeriphInc = DMA_PINC_DISABLE;
    rx_dma.Init.MemInc = DMA_MINC_ENABLE;
    rx_dma.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    rx_dma.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    rx_dma.Init.Mode = DMA_CIRCULAR;
    rx_dma.Init.Priority = DMA_PRIORITY_HIGH;
    rx_dma.Init.FIFOMode = DMA_FIFOMODE_DISABLE;
    check(HAL_DMA_Init(&rx_dma), 7);
    uart.Instance = USART3;
    uart.Init.BaudRate = 460800;
    uart.Init.WordLength = UART_WORDLENGTH_8B;
    uart.Init.StopBits = UART_STOPBITS_1;
    uart.Init.Parity = UART_PARITY_NONE;
    uart.Init.Mode = UART_MODE_TX_RX;
    uart.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    uart.Init.OverSampling = UART_OVERSAMPLING_16;
    uart.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    uart.Init.ClockPrescaler = UART_PRESCALER_DIV1;
    __HAL_LINKDMA(&uart, hdmarx, rx_dma);
    check(HAL_UART_Init(&uart), 8);
    check(HAL_UARTEx_DisableFifoMode(&uart), 9);
    HAL_NVIC_SetPriority(DMA1_Stream0_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(DMA1_Stream0_IRQn);
    HAL_NVIC_SetPriority(USART3_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(USART3_IRQn);
    memset(rx_bytes, 0, sizeof(rx_bytes));
    check(HAL_UARTEx_ReceiveToIdle_DMA(&uart, rx_bytes, sizeof(rx_bytes)), 10);
}

static void timer_init(void) {
    /* PG2 = ZIO D49 / CN8 pin 14; instrumentation only, no actuator. */
    __HAL_RCC_GPIOG_CLK_ENABLE();
    GPIOG->BSRR = GPIO_PIN_2 << 16;
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_2;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOG, &gpio);
    __HAL_RCC_TIM6_CLK_ENABLE();
    timer.Instance = TIM6;
    /* APB1 is /2, hence its timer clock is 2*PCLK1 = 260 MHz. */
    timer.Init.Prescaler = 259;
    timer.Init.CounterMode = TIM_COUNTERMODE_UP;
    timer.Init.Period = 999;
    timer.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    check(HAL_TIM_Base_Init(&timer), 11);
    __HAL_TIM_CLEAR_FLAG(&timer, TIM_FLAG_UPDATE);
    HAL_NVIC_SetPriority(TIM6_DAC_IRQn, 0, 0);
    /* Lockstep has no timer dispatcher, including no background heartbeat. */
    TIM6->CR1 = 0;
    TIM6->DIER = 0;
    HAL_NVIC_DisableIRQ(TIM6_DAC_IRQn);
    HAL_NVIC_ClearPendingIRQ(TIM6_DAC_IRQn);
}
static uint32_t cycles(void) { return DWT->CYCCNT; }
static uint8_t receive_byte(uint32_t start, int waiting_for_first) {
    while (rx_produced == rx_consumed) {
        if (uart_error)
            fatal(20);
        if (!waiting_for_first && HAL_GetTick() - start > 2000)
            fatal(21);
        __WFI();
    }
    if (uart_error || rx_produced - rx_consumed > sizeof(rx_bytes))
        fatal(22);
    __DMB();
    uint8_t value = rx_bytes[rx_consumed % sizeof(rx_bytes)];
    rx_consumed++;
    return value;
}

int main(void) {
    paint_stack();
    /* Instruction cache enabled; D-cache disabled so DMA SRAM stays coherent. */
    SCB_EnableICache();
    SCB_DisableDCache();
    HAL_Init();
    clock_init();
    __set_FPSCR(0); /* round-to-nearest, no flush-to-zero/default-NaN. */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->LAR = 0xc5acce55u;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    if (DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk)
        fatal(13);
    flash_bytes = (uint32_t)((uintptr_t)&_flash_image_end - 0x08000000u);
    flash_crc = ~vv_crc32_update(0xffffffffu, (const uint8_t *)0x08000000u, flash_bytes);
    uart_init();
    timer_init();
    uint8_t info[VV_INFO_SIZE] = {0};
    info[0] = 1;
    info[1] = 1;
    info[2] = 3;
    vv_put32(info + 4, SystemCoreClock);
    vv_put32(info + 8, 2 * HAL_RCC_GetPCLK1Freq());
    vv_put32(info + 12, VV_TICKS);
    memcpy(info + 16, VV_BUILD_GIT, 40);
    memcpy(info + 56, VV_CONTROLLER_SOURCE_SHA256, 64);
    vv_put32(info + 120, HAL_GetUIDw0());
    vv_put32(info + 124, HAL_GetUIDw1());
    vv_put32(info + 128, HAL_GetUIDw2());
    vv_put32(info + 132, DBGMCU->IDCODE);
    vv_put32(info + 136, SCB->CPUID);
    vv_device_init(&device, info);
    vv_replay_init(&replay, &device, replay_inputs, &replay_telemetry, &replay_timing);
    for (;;) {
        assert_dispatch_mode(0);
        uint8_t wire[VV_MAX_FRAME];
        VvFrame request, response;
        wire[0] = receive_byte(0, 1);
        uint32_t start = HAL_GetTick();
        for (size_t i = 1; i < 10; i++)
            wire[i] = receive_byte(start, 0);
        size_t length = (size_t)wire[4] | ((size_t)wire[5] << 8);
        if (length > VV_MAX_PAYLOAD)
            fatal(23);
        for (size_t i = 10; i < length + 12; i++)
            wire[i] = receive_byte(start, 0);
        if (vv_decode(wire, length + 12, &request))
            fatal(24);
        diagnostics();
        vv_replay_handle(&replay, &request, &response, cycles);
        size_t count = vv_encode(&response, wire);
        if (!count)
            fatal(25);
        check(HAL_UART_Transmit(&uart, wire, (uint16_t)count, 2000), 26);
        if (replay.armed) {
            /* ACK fully transmitted first. No UART code or sleep during replay. */
            __disable_irq();
            TIM6->CR1 = 0;
            TIM6->CNT = 0;
            TIM6->EGR = TIM_EGR_UG; /* Restart the prescaler as well as CNT. */
            __HAL_TIM_CLEAR_FLAG(&timer, TIM_FLAG_UPDATE);
            HAL_NVIC_ClearPendingIRQ(TIM6_DAC_IRQn);
            HAL_NVIC_DisableIRQ(DMA1_Stream0_IRQn);
            HAL_NVIC_DisableIRQ(USART3_IRQn);
            TIM6->DIER = TIM_DIER_UIE;
            HAL_NVIC_EnableIRQ(TIM6_DAC_IRQn);
            timed_window = 1;
            assert_dispatch_mode(1);
            timer_ticks = 0;
            uint32_t low = cycles();
            TIM6->CR1 = TIM_CR1_CEN;
            __DSB();
            uint32_t high = cycles();
            vv_replay_arm(&replay, low, high, SystemCoreClock / 1000u);
            __enable_irq();
            while (replay.state == 1)
                __NOP();
            __DMB();
            __disable_irq();
            TIM6->CR1 = 0;
            TIM6->DIER = 0;
            HAL_NVIC_DisableIRQ(TIM6_DAC_IRQn);
            __HAL_TIM_CLEAR_FLAG(&timer, TIM_FLAG_UPDATE);
            HAL_NVIC_ClearPendingIRQ(TIM6_DAC_IRQn);
            timed_window = 0;
            vv_replay_seal_telemetry(&replay);
            diagnostics();
            HAL_NVIC_EnableIRQ(DMA1_Stream0_IRQn);
            HAL_NVIC_EnableIRQ(USART3_IRQn);
            assert_dispatch_mode(0);
            __enable_irq();
        }
    }
}

void SysTick_Handler(void) { HAL_IncTick(); }
void DMA1_Stream0_IRQHandler(void) {
    if (timed_window)
        fatal(28);
    HAL_DMA_IRQHandler(&rx_dma);
}
void USART3_IRQHandler(void) {
    if (timed_window)
        fatal(29);
    HAL_UART_IRQHandler(&uart);
}
/* Two loads before the C prologue; exception stacking precedes this timestamp.
 */
__attribute__((naked)) void TIM6_DAC_IRQHandler(void) {
    __asm volatile("ldr r0, =0xe0001004\n"
                   "ldr r0, [r0]\n"
                   "b tim6_body\n");
}
void tim6_body(uint32_t entry) {
    if (!(TIM6->SR & TIM_SR_UIF))
        return;
    __HAL_TIM_CLEAR_FLAG(&timer, TIM_FLAG_UPDATE);
    GPIOG->BSRR = GPIO_PIN_2;
    assert_dispatch_mode(1);
    last_timer_entry = entry;
    timer_ticks++;
    if (replay.state == 1 && !replay.armed) {
        vv_replay_tick(&replay, entry, cycles);
        uint32_t exit_cycles = cycles();
        int pending = (TIM6->SR & TIM_SR_UIF) != 0;
        vv_replay_exit(&replay, exit_cycles, pending);
        /* Also catch a rollover during the final telemetry bookkeeping. */
        if ((TIM6->SR & TIM_SR_UIF) && !pending) {
            uint32_t k = replay.completed - 1;
            replay.overruns++;
            if (!(replay_telemetry.status[k] & 0x80)) {
                replay_telemetry.status[k] |= 0x80;
                replay.misses++;
            }
        }
        if (replay.state != 1)
            TIM6->CR1 = 0;
        replay_timing.isr_body[replay.completed - 1] = cycles() - entry;
    }
    GPIOG->BSRR = GPIO_PIN_2 << 16;
}
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *handle, uint16_t size) {
    if (handle->Instance == USART3) {
        uint32_t position = size % sizeof(rx_bytes);
        rx_produced += (position + sizeof(rx_bytes) - rx_last_position) % sizeof(rx_bytes);
        rx_last_position = position;
        if (rx_produced - rx_consumed > sizeof(rx_bytes))
            uart_error = 1;
    }
}
void HAL_UART_ErrorCallback(UART_HandleTypeDef *handle) {
    (void)handle;
    uart_error = 1;
}
void HardFault_Handler(void) { fatal(100); }
void MemManage_Handler(void) { fatal(101); }
void BusFault_Handler(void) { fatal(102); }
void UsageFault_Handler(void) { fatal(103); }
void _init(void) {}
void _fini(void) {}
void *_sbrk(ptrdiff_t increment) {
    (void)increment;
    errno = ENOMEM;
    return (void *)-1;
}
