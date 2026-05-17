# SPDX-License-Identifier: MIT

import sys
import utime

try:
    import machine
    cpu_freq_mhz = machine.freq() / 1000000
except Exception:
    cpu_freq_mhz = "unknown"

implementation = getattr(sys, "implementation", None)
machine_name = getattr(implementation, "_machine", "MicroPython board")
board = machine_name.split(" with")[0]

print("Hello, Wokwi!")
print(f"Running on {board} ({sys.platform}) at {cpu_freq_mhz} MHz")

counter = 0
while True:
    counter += 1
    print(f"Uptime: {counter} seconds")
    utime.sleep_ms(1000)