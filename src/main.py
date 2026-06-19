# =============================================================================
# José Herrera Ortiz
# main.py — Entry point: 50 Hz control loop for the Raspberry Pi RC Car
# Raspberry Pi 3 RC Car
# =============================================================================
# Run  :  python main.py
# Stop :  Ctrl+C  (shuts down motors and releases GPIO cleanly)
# =============================================================================

from time import sleep

import constants       as cst
from car            import Car
from ultrasonic     import UltrasonicSensor
from web_controller import start_server, read_state


def main() -> None:
    """Initialise hardware and run the main control loop at ~50 Hz.

    Each iteration performs the following steps in order:

    1. **Read controller** — fetch the latest direction, acceleration and
       reverse flag from the web interface.
    2. **Read sensors** — measure obstacle distance (HC-SR04) and ambient
       light voltage (LDR via MCP3008).
    3. **LED** — compute and apply automatic brightness from light voltage.
    4. **Speed cap** — in forward mode the proximity table limits the base
       speed proportionally to the obstacle distance; in reverse mode no
       cap is applied (the driver has full visibility behind them).
    5. **Steering** — split the base speed into left/right wheel duties
       using the differential-drive model.
    6. **Drive** — send the resulting duty cycles to the motors.
    7. **Telemetry** — print a live one-line status to stdout.
    """
    car = Car()
    proximity_sensor = UltrasonicSensor(
        trigger_pin=cst.ULTRASONIC_TRIGGER_PIN,
        echo_pin=cst.ULTRASONIC_ECHO_PIN,
    )

    try:
        start_server(host="0.0.0.0", port=8080)
        print("Web server started.")
        print("Open on your phone: http://<RASPBERRY_PI_IP>:8080\n")

        while True:
            # Step 1: Read web controller
            state          = read_state()
            direction      = float(state["direction"])
            acceleration   = float(state["acceleration"])
            reverse_active = bool(state["reverse"])

            # Step 2: Read sensors
            distance_cm   = proximity_sensor.measure_distance()
            light_voltage = car.read_sensor_voltage()

            # Step 3: Automatic LED brightness
            led_brightness = car.compute_led_brightness(light_voltage)
            car.update_led(led_brightness)

            # Step 4: Compute speed-limited base speed
            if reverse_active:
                # Obstacle avoidance disabled in reverse (capped at MAX_REVERSE_SPEED)
                base_speed = acceleration * cst.MAX_REVERSE_SPEED
            else:
                if distance_cm is None:
                    max_allowed_speed = 0.0  # Sensor timeout → full stop
                else:
                    max_allowed_speed = car.compute_speed_limit(distance_cm)
                base_speed = acceleration * max_allowed_speed

            # Step 5: Differential steering
            speed_left, speed_right = car.compute_wheel_speeds(base_speed, direction)

            # Step 6: Drive or stop
            if base_speed <= cst.STOP_THRESHOLD:
                car.stop_motors()
            else:
                car.drive(speed_left, speed_right, reverse=reverse_active)

            # Step 7: Live telemetry
            dist_str = f"{distance_cm:5.1f} cm" if distance_cm is not None else "None"
            print(
                f"\rrev={str(reverse_active):<5}  "
                f"dir={direction:+.2f}  "
                f"acc={acceleration:.2f}  "
                f"dist={dist_str}  "
                f"light={light_voltage:.2f} V  "
                f"led={led_brightness:.2f}  "
                f"L={speed_left:.2f}  "
                f"R={speed_right:.2f}     ",
                end="",
                flush=True,
            )

            sleep(cst.MAIN_LOOP_PERIOD)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")

    finally:
        proximity_sensor.close()
        car.shutdown()
        print("System shut down cleanly.")


if __name__ == "__main__":
    main()