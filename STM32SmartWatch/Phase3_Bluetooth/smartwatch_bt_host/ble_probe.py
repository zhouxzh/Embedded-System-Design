"""
Small BLE diagnostic helper for hc05V2.3_le-style modules.

Run:
    python ble_probe.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from bleak import BleakClient, BleakScanner


SCAN_TIMEOUT = float(os.getenv("BLE_SCAN_TIMEOUT", "10.0"))
TARGET_HINT = os.getenv("BLE_TARGET_NAME", "SMARTWATCH")


async def main():
    print(f"Scanning BLE devices for {SCAN_TIMEOUT:.0f}s...")
    named_by_addr = {}

    def on_detect(device, adv):
        name = adv.local_name or device.name or ""
        if name:
            is_new = device.address not in named_by_addr
            named_by_addr[device.address] = (name, device, adv)
            if is_new:
                rssi = getattr(adv, "rssi", None)
                print(f"[scan] {name}  {device.address}  RSSI={rssi}")

    scanner = BleakScanner(detection_callback=on_detect, scanning_mode="active")
    await scanner.start()
    await asyncio.sleep(SCAN_TIMEOUT)
    await scanner.stop()

    named = list(named_by_addr.values())

    if not named:
        print("No named BLE devices found.")
        return 1

    named.sort(key=lambda row: (TARGET_HINT.upper() not in row[0].upper(), row[0], row[1].address))
    print("\nNamed BLE devices:")
    for idx, (name, device, adv) in enumerate(named):
        rssi = getattr(adv, "rssi", None)
        print(f"[{idx}] {name}  {device.address}  RSSI={rssi}")

    selected = None
    for row in named:
        if TARGET_HINT in row[0].upper():
            selected = row
            break
    if selected is None:
        print(f"No {TARGET_HINT} found. Re-power the module and run again.")
        return 2

    name, device, _adv = selected
    print(f"\nConnecting to {name} {device.address} ...")
    try:
        async with BleakClient(device) as client:
            print(f"Connected: {client.is_connected}")
            print("\nServices:")
            for service in client.services:
                print(f"[S] {service.uuid} {service.description}")
                for char in service.characteristics:
                    props = ",".join(char.properties)
                    print(f"  [C] {char.uuid}  {props}  {char.description}")
                    for desc in char.descriptors:
                        print(f"    [D] {desc.uuid} {desc.description}")
            print("\nProbe complete.")
    except Exception as exc:
        print(f"\nConnect/probe failed: {type(exc).__name__}: {exc}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
