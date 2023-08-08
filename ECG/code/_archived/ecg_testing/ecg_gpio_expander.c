
#include "ecg_gpio_expander.h"

// Initialize and connect the GPIO expander via I2C.
int ecg_gpio_expander_setup()
{
  // Initialize I2C/GPIO functionality.
  gpioInitialise();

  // Connect to the GPIO expander.
  ecg_gpio_expander_i2c_device = i2cOpen(ECG_I2C_BUS, ECG_GPIO_EXPANDER_I2C_ADDRESS, 0);
  if(ecg_gpio_expander_i2c_device < 0)
  {
    ECG_LOG("ecg_gpio_expander_setup(): Failed to connect to the GPIO expander: returned %d.", ecg_gpio_expander_i2c_device);
    switch(ecg_gpio_expander_i2c_device)
    {
      case(PI_BAD_I2C_BUS): ECG_LOG(" (PI_BAD_I2C_BUS)"); break;
      case(PI_BAD_I2C_ADDR): ECG_LOG(" (PI_BAD_I2C_ADDR)"); break;
      case(PI_BAD_FLAGS): ECG_LOG(" (PI_BAD_FLAGS)"); break;
      case(PI_NO_HANDLE): ECG_LOG(" (PI_NO_HANDLE)"); break;
      case(PI_I2C_OPEN_FAILED): ECG_LOG(" (PI_I2C_OPEN_FAILED)"); break;
      default: ECG_LOG(" (UNKNOWN CODE)"); break;
    }
    ECG_LOG("\n");
    return 0;
  }
  ECG_LOG("ecg_gpio_expander_setup(): GPIO expander connected successfully!\n");

  // Note that all ports are inputs by default at power-on.
  // The below (untested) code should also set them all to inputs,
  //   but will also cause strong pullups to be briefly connected (during HIGH time of the acknowledgment pulse).
  //   To avoid this for now, the default state is leveraged and no commands are sent.
  //i2cWriteByte(ecg_gpio_expander_i2c_device, 0b11111111) // set all to inputs (1 = weakly driven high)

  return 1;
}

// Terminate the I2C connection.
void ecg_gpio_expander_cleanup()
{
  ECG_LOG("ecg_gpio_expander_cleanup(): Terminating the GPIO interface.\n");
  gpioTerminate();
}

// Read all inputs of the GPIO expander.
int ecg_gpio_expander_read()
{
  int result = i2cReadByte(ecg_gpio_expander_i2c_device);
  switch(result)
  {
    case(PI_BAD_HANDLE): ECG_LOG("ecg_gpio_expander_read(): Failed to read (PI_BAD_HANDLE).\n"); break;
    case(PI_I2C_READ_FAILED): ECG_LOG("ecg_gpio_expander_read(): Failed to read (PI_I2C_READ_FAILED).\n"); break;
    default: break;
  }
  return result;
}

// Read the ADC data-ready output bit.
// Will first read all inputs of the GPIO expander, then extract the desired bit.
int ecg_gpio_expander_read_dataReady()
{
  return ecg_gpio_expander_parse_dataReady(ecg_gpio_expander_read());
}

// Read the ECG leads-off detection output bit.
// Will first read all inputs of the GPIO expander, then extract the desired bit.
int ecg_gpio_expander_read_lod()
{
  return ecg_gpio_expander_parse_lod(ecg_gpio_expander_read());
}

// Given a byte of all GPIO expander inputs, extract the ADC data-ready bit.
int ecg_gpio_expander_parse_dataReady(uint8_t data)
{
  return (data >> ECG_GPIO_EXPANDER_CHANNEL_DATAREADY) & 0b00000001;
}

// Given a byte of all GPIO expander inputs, extract the ECG leads-off detection bit.
int ecg_gpio_expander_parse_lod(uint8_t data)
{
  return (data >> ECG_GPIO_EXPANDER_CHANNEL_LOD) & 0b00000001;
}



