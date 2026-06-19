# =============================================================================
# José Herrera Ortiz
# constants.py — Hardware configuration and tuning parameters
# Raspberry Pi 3 RC Car
# =============================================================================
# Edit this file to match your wiring before running the project.
# All GPIO numbers use BCM (Broadcom) numbering.
# =============================================================================

# ── ADC — MCP3008 via hardware SPI  
ADC_VREF = 3.3                  # ADC reference voltage (V); must match Vdd pin

LIGHT_SENSOR_CHANNEL = 0        # MCP3008 channel wired to the LDR voltage divider

# Ultrasonic distance sensor — HC-SR04
ULTRASONIC_TRIGGER_PIN = 20     # BCM GPIO pin connected to TRIG
ULTRASONIC_ECHO_PIN    = 21     # BCM GPIO pin connected to ECHO

# Speed-vs-distance look-up table
# Maps obstacle distance (cm) to the maximum allowed forward speed [0.0, 1.0].
# Intermediate values are linearly interpolated.
# IMPORTANT: points must be sorted from HIGHEST to LOWEST distance.
PROXIMITY_TABLE_CM = [
    (100.0, 1.0 ),   # >= 100 cm  →  full speed allowed
    ( 80.0, 0.9 ),
    ( 60.0, 0.7 ),
    ( 40.0, 0.5 ),
    ( 25.0, 0.3 ),
    ( 15.0, 0.15),
    (  8.0, 0.0 ),   # <= 8 cm    →  forced stop
]

# Motor PWM — rpi-hardware-pwm 
# Hardware PWM channels map to fixed GPIO pins on Raspberry Pi 3:
#   Channel 0  →  GPIO 18   (requires dtoverlay=pwm-2chan in /boot/config.txt)
#   Channel 1  →  GPIO 19
LEFT_MOTOR_PWM_CHANNEL  = 0
RIGHT_MOTOR_PWM_CHANNEL = 1
MOTOR_PWM_FREQ          = 1000  # PWM carrier frequency (Hz)

# Motor direction pins — L298N H-bridge IN1 / IN2
LEFT_MOTOR_IN1_PIN  = 4
LEFT_MOTOR_IN2_PIN  = 5
RIGHT_MOTOR_IN1_PIN = 6
RIGHT_MOTOR_IN2_PIN = 12

# Set to True if a motor spins in the wrong direction with the default wiring
INVERT_LEFT_MOTOR  = True
INVERT_RIGHT_MOTOR = True

# LED
LED_PIN = 25                    # BCM GPIO pin for the PWM-controlled LED

# Motion control
MAX_REVERSE_SPEED = 0.4         # Maximum duty cycle allowed in reverse (safety cap)
STOP_THRESHOLD    = 0.02        # Speeds below this value are treated as zero
STEERING_GAIN     = 1.0         # Intensity of inner-wheel slowdown during turns
STEERING_DEADZONE = 0.08        # Joystick dead zone around the centre (±, normalised)
MAIN_LOOP_PERIOD  = 0.02        # Control-loop interval in seconds (50 Hz)

# Ambient-light thresholds for automatic LED brightness
# The LED dims linearly between LIGHT_VOLT_MAX and LIGHT_VOLT_OFF,
# and is fully on / fully off outside those bounds.
LIGHT_VOLT_OFF = 1.74           # LDR voltage (V) above which the LED turns off
LIGHT_VOLT_MAX = 0.50           # LDR voltage (V) below which the LED is at full brightness

# Reserved — physical joystick support (not used in current version)
CONTROLLER_INTERFACE = "/dev/input/js0"
JOYSTICK_MAX_VALUE   = 32767
TRIGGER_MAX_VALUE    = 32767
TRIGGER_MIN_VALUE    = -32767
