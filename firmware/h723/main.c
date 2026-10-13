/* Development-board controller only. MuJoCo is the plant; no actuator pins. */
#include "../protocol/protocol.h"
#include "build_identity.h"
#include "stm32h7xx_hal.h"
#include <errno.h>
#include <string.h>

UART_HandleTypeDef uart;
DMA_HandleTypeDef rx_dma;
TIM_HandleTypeDef timer;
static VvDevice device;
volatile uint32_t board_error, timer_ticks, last_timer_entry;
static volatile uint32_t rx_produced, rx_consumed, uart_error;
static uint32_t rx_last_position;
static uint8_t rx_bytes[512] __attribute__((section(".dma"), aligned(32)));

/* Reserve the complete B2 budget now. B1 advertises lockstep only. */
CtrlSensors replay_inputs[VV_TICKS] __attribute__((section(".replay_inputs"), used, aligned(32)));
typedef struct {
    float force[VV_TICKS];
    uint32_t entry[VV_TICKS], compute[VV_TICKS];
    uint8_t status[VV_TICKS];
} ReplayTelemetry;
ReplayTelemetry replay_telemetry __attribute__((section(".telemetry"), used, aligned(8)));
_Static_assert(sizeof(CtrlSensors) == 32 && sizeof(ReplayTelemetry) == 104000, "replay RAM budget");

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
    HAL_NVIC_EnableIRQ(TIM6_DAC_IRQn);
    check(HAL_TIM_Base_Start_IT(&timer), 12);
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
    uart_init();
    timer_init();
    uint8_t info[VV_INFO_SIZE] = {0};
    info[0] = 1;
    info[1] = 1;
    info[2] = 1;
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
    for (;;) {
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
        vv_handle(&device, &request, &response, cycles);
        size_t count = vv_encode(&response, wire);
        if (!count)
            fatal(25);
        check(HAL_UART_Transmit(&uart, wire, (uint16_t)count, 2000), 26);
    }
}

void SysTick_Handler(void) { HAL_IncTick(); }
void DMA1_Stream0_IRQHandler(void) { HAL_DMA_IRQHandler(&rx_dma); }
void USART3_IRQHandler(void) { HAL_UART_IRQHandler(&uart); }
void TIM6_DAC_IRQHandler(void) { HAL_TIM_IRQHandler(&timer); }
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *handle) {
    if (handle->Instance == TIM6) {
        last_timer_entry = cycles();
        timer_ticks++;
    }
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
