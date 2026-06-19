# =============================================================================
# José Herrera Ortiz
# car.py — Car class: dual DC motors, PWM LED, and ambient-light sensor
# Raspberry Pi 3 RC Car
# =============================================================================

from gpiozero import OutputDevice, PWMLED, MCP3008
from rpi_hardware_pwm import HardwarePWM

import constants as cst


class Car:
    """Controls the two DC motors, the ambient-light-reactive LED, and reads
    the LDR (light-dependent resistor) voltage via the MCP3008 ADC.

    Hardware overview
    -----------------
    * L298N dual H-bridge   — motor direction via IN1/IN2 pins on each side
    * rpi-hardware-pwm      — hardware PWM for motor speed (GPIO 18 & GPIO 19)
    * MCP3008 (SPI)         — 10-bit ADC for reading the LDR voltage divider
    * gpiozero PWMLED       — software-PWM LED for automatic brightness control

    Usage
    -----
    >>> car = Car()
    >>> car.drive(speed_left=0.6, speed_right=0.6)   # drive straight
    >>> car.stop_motors()
    >>> car.shutdown()                                 # always call on exit
    """

    def __init__(self) -> None:
        # Analogue light sensor via MCP3008 hardware SPI
        self.light_sensor = MCP3008(channel=cst.LIGHT_SENSOR_CHANNEL)
        self.led           = PWMLED(cst.LED_PIN)

        # Motor direction pins (H-bridge IN1 / IN2, one pair per side)
        self.left_motor_in1  = OutputDevice(cst.LEFT_MOTOR_IN1_PIN)
        self.left_motor_in2  = OutputDevice(cst.LEFT_MOTOR_IN2_PIN)
        self.right_motor_in1 = OutputDevice(cst.RIGHT_MOTOR_IN1_PIN)
        self.right_motor_in2 = OutputDevice(cst.RIGHT_MOTOR_IN2_PIN)

        # Hardware PWM for motor speed — must start at 0 % duty cycle
        self.pwm_left  = HardwarePWM(pwm_channel=cst.LEFT_MOTOR_PWM_CHANNEL,  hz=cst.MOTOR_PWM_FREQ)
        self.pwm_right = HardwarePWM(pwm_channel=cst.RIGHT_MOTOR_PWM_CHANNEL, hz=cst.MOTOR_PWM_FREQ)
        self.pwm_left.start(0)
        self.pwm_right.start(0)

        # Internal state (used by is_stopped and for diagnostics)
        self.last_reverse_mode = False
        self.last_speed_left   = 0.0
        self.last_speed_right  = 0.0

        self.stop_motors()

    # Utility helpers
    def clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        """Return *value* clamped to the closed interval [*low*, *high*]."""
        if value < low:
            return low
        if value > high:
            return high
        return value

    def lookup_table(self, x: float, points: list) -> float:
        """Linearly interpolate *x* in a look-up table of (x, y) pairs.

        Parameters
        ----------
        x      : Query value.
        points : List of (x, y) tuples sorted from *highest* to *lowest* x.
                 Must contain at least one entry.

        Returns
        -------
        Interpolated y value; clamped to the nearest endpoint outside range.
        """
        if not points:
            raise ValueError("Look-up table must contain at least one point.")

        if x >= points[0][0]:
            return points[0][1]

        if x <= points[-1][0]:
            return points[-1][1]

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            if x1 >= x >= x2:
                if x1 == x2:
                    return y1
                t = (x - x2) / (x1 - x2)
                return y2 + t * (y1 - y2)

        return points[-1][1]

    # Sensor reads
    def read_sensor_voltage(self) -> float:
        """Return the current LDR voltage in volts (range: 0 V - ADC_VREF)."""
        return self.light_sensor.value * cst.ADC_VREF

    # Computed quantities
    def compute_speed_limit(self, distance_cm: float) -> float:
        """Return the maximum allowed forward speed [0.0, 1.0] for the given
        obstacle distance, using the proximity look-up table in constants.py."""
        speed = self.lookup_table(distance_cm, cst.PROXIMITY_TABLE_CM)
        return self.clamp(speed)

    def compute_led_brightness(self, voltage: float) -> float:
        """Convert the LDR voltage to an LED brightness level (0.0 - 1.0).

        The LED is brightest in darkness (low voltage) and fully off in
        daylight (high voltage), providing automatic ambient-light compensation.

        Returns 0.0 if voltage >= LIGHT_VOLT_OFF
        Returns 1.0 if voltage <= LIGHT_VOLT_MAX
        Linear interpolation in between.
        """
        if voltage >= cst.LIGHT_VOLT_OFF:
            return 0.0
        if voltage <= cst.LIGHT_VOLT_MAX:
            return 1.0
        brightness = (cst.LIGHT_VOLT_OFF - voltage) / (cst.LIGHT_VOLT_OFF - cst.LIGHT_VOLT_MAX)
        return self.clamp(brightness)

    def compute_wheel_speeds(self, base_speed: float, steering: float) -> tuple:
        """Convert a linear speed and a steering command into wheel duty cycles.

        The inner wheel is slowed by (|steering| x STEERING_GAIN) while the
        outer wheel keeps *base_speed*, producing a smooth differential turn.

        Parameters
        ----------
        base_speed : Desired forward speed [0.0, 1.0].
        steering   : Lateral command [-1.0, 1.0].
                     Negative values turn LEFT (slow left wheel).
                     Positive values turn RIGHT (slow right wheel).

        Returns
        -------
        (speed_left, speed_right) : Independent duty cycles, both in [0.0, 1.0].
        """
        base_speed = self.clamp(base_speed)
        steering   = self.clamp(steering, -1.0, 1.0)

        # Ignore tiny joystick offsets inside the dead zone
        if abs(steering) < cst.STEERING_DEADZONE:
            steering = 0.0

        reduction   = self.clamp(abs(steering) * cst.STEERING_GAIN)
        speed_left  = base_speed
        speed_right = base_speed

        if steering < 0:  # Turn left: slow the left wheel
            speed_left  = base_speed * (1.0 - reduction)
        elif steering > 0:  # Turn right: slow the right wheel
            speed_right = base_speed * (1.0 - reduction)

        return self.clamp(speed_left), self.clamp(speed_right)

    # Output setters
    def update_led(self, brightness: float) -> None:
        """Set the LED to *brightness* (0.0 = off, 1.0 = maximum)."""
        self.led.value = self.clamp(brightness)

    def _set_left_direction(self, forward: bool = True) -> None:
        """Drive the left H-bridge IN1/IN2 pins for the requested direction.
        Applies INVERT_LEFT_MOTOR from constants if the motor is wired in reverse.
        """
        actual_forward = (not forward) if cst.INVERT_LEFT_MOTOR else forward
        if actual_forward:
            self.left_motor_in1.on()
            self.left_motor_in2.off()
        else:
            self.left_motor_in1.off()
            self.left_motor_in2.on()

    def _set_right_direction(self, forward: bool = True) -> None:
        """Drive the right H-bridge IN1/IN2 pins for the requested direction.
        Applies INVERT_RIGHT_MOTOR from constants if the motor is wired in reverse.
        """
        actual_forward = (not forward) if cst.INVERT_RIGHT_MOTOR else forward
        if actual_forward:
            self.right_motor_in1.on()
            self.right_motor_in2.off()
        else:
            self.right_motor_in1.off()
            self.right_motor_in2.on()

    def _set_left_speed(self, speed: float) -> None:
        """Write *speed* (0.0 – 1.0) as a duty-cycle percentage to the left
        motor hardware PWM channel (0 % – 100 %)."""
        self.pwm_left.change_duty_cycle(self.clamp(speed) * 100.0)

    def _set_right_speed(self, speed: float) -> None:
        """Write *speed* (0.0 – 1.0) as a duty-cycle percentage to the right
        motor hardware PWM channel (0 % – 100 %)."""
        self.pwm_right.change_duty_cycle(self.clamp(speed) * 100.0)

    # High-level motor commands
    def drive(self, speed_left: float, speed_right: float, reverse: bool = False) -> None:
        """Apply independent wheel speeds in the given direction.

        Speeds below STOP_THRESHOLD are zeroed.  If both are zero after
        clamping, the call is forwarded to stop_motors().

        Parameters
        ----------
        speed_left  : Left wheel duty cycle [0.0, 1.0].
        speed_right : Right wheel duty cycle [0.0, 1.0].
        reverse     : ``True`` to drive both motors in reverse.
        """
        speed_left  = self.clamp(speed_left)
        speed_right = self.clamp(speed_right)

        # Treat near-zero values as full stop to avoid motor jitter
        if speed_left  < cst.STOP_THRESHOLD: speed_left  = 0.0
        if speed_right < cst.STOP_THRESHOLD: speed_right = 0.0

        if speed_left == 0.0 and speed_right == 0.0:
            self.stop_motors()
            return

        self._set_left_direction(forward=not reverse)
        self._set_right_direction(forward=not reverse)
        self._set_left_speed(speed_left)
        self._set_right_speed(speed_right)

        self.last_reverse_mode = reverse
        self.last_speed_left   = speed_left
        self.last_speed_right  = speed_right

    def stop_motors(self) -> None:
        """Set both PWM channels to 0 % and de-energise all direction pins."""
        self._set_left_speed(0.0)
        self._set_right_speed(0.0)
        self.left_motor_in1.off()
        self.left_motor_in2.off()
        self.right_motor_in1.off()
        self.right_motor_in2.off()
        self.last_speed_left  = 0.0
        self.last_speed_right = 0.0

    def is_stopped(self) -> bool:
        """Return ``True`` if both motors are at or below STOP_THRESHOLD."""
        return (
            self.last_speed_left  < cst.STOP_THRESHOLD and
            self.last_speed_right < cst.STOP_THRESHOLD
        )

    def shutdown(self) -> None:
        """Stop motors, switch off the LED, and release hardware PWM resources.

        Always call this before exiting to avoid leaving the motors energised.
        """
        self.stop_motors()
        self.update_led(0.0)
        self.pwm_left.stop()
        self.pwm_right.stop()