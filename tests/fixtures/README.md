# Vendor simulation captures

These JSON files are actual HTTP responses from CTRE Phoenix Diagnostics 26.3.0 in `CTR_TARGET=Simulation`, captured during protocol research on 2026-10-15. They are used for deterministic parser and validation tests. They are not production device readings or an application simulation backend. Runtime simulation uses the actual vendor SDK.

The initial capture process created Talon FX ID 1, CANcoder ID 2 and Pigeon 2 ID 3. The application simulation uses eight devices, so its IDs differ from these initial captures.

Configuration descriptions and signal metadata originate from CTRE's SDK and retain their vendor copyright. See [the vendor license](../../docs/licenses/CTRE_LICENSE.txt) and [notices](../../THIRD_PARTY_NOTICES.md). No device firmware or vendor executables are stored in these fixtures.

`plotpro.json` and `getcontrols.json` were captured from the current eight-device simulation, Talon FX ID 1. Plot ordinals 290–339 are actual buffered server records; control metadata covers 44 advertised request types.
