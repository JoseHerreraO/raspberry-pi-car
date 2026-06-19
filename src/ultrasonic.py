# =============================================================================
# José Herrera Ortiz
# ultrasonic.py — HC-SR04 ultrasonic distance sensor driver
# Raspberry Pi 3 RC Car
# =============================================================================

from time    import sleep, perf_counter
from gpiozero import OutputDevice, InputDevice


class UltrasonicSensor:
    """Non-blocking driver for the HC-SR04 ultrasonic distance sensor.

    Operating principle
    -------------------
    Pulsing the TRIG pin HIGH for 10 µs triggers a burst of 8 x 40 kHz
    ultrasound pulses.  The ECHO pin then goes HIGH for a duration equal to
    the sound's round-trip travel time.  Distance is derived as:

        distance (cm) = (echo_duration x speed_of_sound) / 2
                      = (echo_duration x 34 300 cm/s)    / 2

    The timeout guard prevents indefinite blocking if the echo is never
    received (obstacle out of range, or sensor not connected).

    Parameters
    ----------
    trigger_pin : BCM GPIO number wired to the TRIG pin of the HC-SR04.
    echo_pin    : BCM GPIO number wired to the ECHO pin of the HC-SR04.
    timeout     : Maximum time (seconds) to wait for an echo before returning
                  ``None``.  Defaults to 20 ms (~344 cm max range).

    Usage
    -----
    >>> sensor = UltrasonicSensor(trigger_pin=20, echo_pin=21)
    >>> distance = sensor.measure_distance()   # returns float | None
    >>> sensor.close()
    """

    def __init__(self, trigger_pin: int, echo_pin: int, timeout: float = 0.02) -> None:
        self.trigger = OutputDevice(trigger_pin, initial_value=False)
        self.echo    = InputDevice(echo_pin)
        self.timeout = timeout

    def measure_distance(self) -> float | None:
        """Trigger one measurement and return the obstacle distance in cm.

        Returns "None" if no echo is received within the timeout window
        (obstacle too far, or sensor error).
        """
        # Ensure TRIG is LOW before firing to avoid a false start
        self.trigger.off()
        sleep(0.000002)

        # Send a 10 µs HIGH pulse to start the ultrasound burst
        self.trigger.on()
        sleep(0.00001)
        self.trigger.off()

        deadline = perf_counter() + self.timeout  # Absolute timeout guard

        # Phase 1: wait for ECHO to go HIGH (start of return pulse)
        while self.echo.value == 0:
            if perf_counter() > deadline:
                return None  # No echo received in time

        echo_start = perf_counter()

        # Phase 2: wait for ECHO to go LOW (end of return pulse)
        while self.echo.value == 1:
            if perf_counter() > deadline:
                return None  # Echo held HIGH too long

        echo_end = perf_counter()

        # Convert round-trip time to distance using the speed of sound
        duration    = echo_end - echo_start
        distance_cm = (duration * 34300.0) / 2.0
        return distance_cm

    def close(self) -> None:
        """Release the GPIO pins used by this sensor."""
        self.trigger.close()
        self.echo.close()


if __name__ == "__main__":
    sensor = UltrasonicSensor(trigger_pin=20, echo_pin=21)
    print("HC-SR04 test — press Ctrl+C to stop.\n")
    try:
        while True:
            reading = sensor.measure_distance()
            if reading is not None:
                print(f"{reading:6.1f} cm", end="\r")
            else:
                print(" Out of range ", end="\r")
            sleep(0.1)
    except KeyboardInterrupt:
        sensor.close()
        print("\nSensor closed.")