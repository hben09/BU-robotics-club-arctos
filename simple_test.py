#!/usr/bin/env python3
"""
Move MKS SERVO42D/57D motor 90 degrees via CANable on Fedora.

Setup first:
    sudo dnf install can-utils
    pip3 install python-can
    sudo modprobe gs_usb
    sudo ip link set can0 type can bitrate 500000
    sudo ip link set can0 up

Then run:
    sudo python3 move_90deg.py
"""

import can
import time
import sys

CAN_ID  = 0x01       # Motor CAN ID (default)
BITRATE = 500000     # 500K (default)

def crc(can_id, data):
    return (can_id + sum(data)) & 0xFF

def send(bus, data):
    payload = list(data) + [crc(CAN_ID, data)]
    msg = can.Message(arbitration_id=CAN_ID, data=payload, is_extended_id=False)
    bus.send(msg)
    print(f"  TX: {' '.join(f'{b:02X}' for b in payload)}")
    # wait for response
    resp = bus.recv(timeout=2.0)
    if resp and resp.arbitration_id == CAN_ID:
        print(f"  RX: {' '.join(f'{b:02X}' for b in resp.data)}")
        return list(resp.data)
    print("  RX: (no response)")
    return None

bus = can.Bus(interface="socketcan", channel="can0", bitrate=BITRATE)

try:
    # 1. Set mode to SR_vFOC (bus FOC mode)
    print("[1] Setting bus FOC mode...")
    send(bus, [0x82, 0x05])
    time.sleep(0.2)

    # 2. Enable motor
    print("[2] Enabling motor...")
    send(bus, [0xF3, 0x01])
    time.sleep(0.2)

    # 3. Move 90 degrees using relative pulses
    #    16 microsteps * 200 steps = 3200 pulses/rev
    #    90° = 3200 / 4 = 800 pulses = 0x000320
    print("[3] Moving 90° CW...")
    #    cmd=0xFD, dir=CW(1)|speed_hi, speed_lo, acc, pulse[2:0]
    #    speed = 300 RPM = 0x12C → hi=0x01, lo=0x2C
    #    acc = 10
    #    pulses = 800 = 0x000320
    send(bus, [0xFD, 0x81, 0x2C, 0x0A, 0x00, 0x03, 0x20])

    # 4. Wait for it to finish
    print("[4] Waiting for move to complete...")
    deadline = time.time() + 10
    while time.time() < deadline:
        resp = bus.recv(timeout=2.0)
        if resp and resp.arbitration_id == CAN_ID:
            print(f"  RX: {' '.join(f'{b:02X}' for b in resp.data)}")
            if resp.data[0] == 0xFD and resp.data[1] == 0x02:
                print("[✓] Move complete!")
                break
    else:
        print("[i] Timed out waiting — motor may still be moving or response disabled.")

    print("Done.")

except KeyboardInterrupt:
    print("\nStopping...")
    send(bus, [0xF7])  # emergency stop
finally:
    bus.shutdown()