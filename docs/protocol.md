# Verified Phoenix Diagnostics protocol

Tested locally on 2026-10-15 with **phoenix6 26.3.0**, Linux x86-64, `CTR_TARGET=Simulation`. Vendor server reports `2026.3.0 (May 22 2026, 21:24:16)`, compliancy 19. Tests use real vendor simulation, not an invented HTTP emulator. Hardware transport behavior and older releases remain unverified.

## Requests

HTTP `GET /?action=...&model=...&id=...&canbus=...` on port **1250**. Use the exact **Model** and **CANbus** strings returned by discovery, properly URL encoded. A guessed `TalonFX` or `talonfx` model fails with -120; a reported `Talon FX vers. C` succeeds. Device identity also includes serial locally. Duplicate ID resolution is not implemented: mutations of ambiguous devices must be avoided.

Every supported response includes `GeneralReturn.Error` and `ErrorMessage`. HTTP 200 alone is not success. Unknown response shapes are rejected. Timeouts are bounded; writes are never automatically retried.

| Action | Verified response / parameters |
|---|---|
| `getversion` | `Version`, `System`, `Compliancy`, `SearchDirectory` |
| `getdevices` | `DeviceArray` with `Model`, `ID`, `CANbus`, `Name`, `CurrentVers`, `SerialNo`, `SoftStatus` and capability flags |
| `getsignals` | `Signals`: `Id`, `Name`, `Units`, `Summary` |
| `plotpro` | `signals=<comma-separated SPNs>`, `resolution=1000`; overlapping timestamped record ring, described below |
| `getcontrols` | `Controls` object keyed by request type, with constructor parameter metadata |
| `controlv2` | Typed GET parameters, `controlmode`, `controlen`; described below |
| `getsignalvalue` | `signals=1781,1782`; `Values` object keyed by signal ID. Comma-separated decimal IDs, not a JSON array |
| `decoratedselftest` | `SelfTest` object keyed by SPN, each with `Value` (string) and `Units` |
| `getconfigv2` | `JsonVersion: 2`, `Device`: array of groups, each with `Configs` metadata |
| `setconfigv2` | Custom POST below, returns configuration and status; app separately refreshes afterward |
| `blink` | Also clears sticky faults; user confirmation required |
| `setname` | `newname`, success status and `NewName` |
| `setid` | `newid`; request format from the official reference client, ID range 0–62. The 26.3.0 simulator rejects changes with -109; successful physical ID changes remain unverified |

Self-test names are joined against the signal catalog; unknown IDs are shown as `SPN n`, not guessed. `getsignalvalue` remains available for point readback but no longer powers plotting.

## Buffered plotting

`GET action=plotpro&model=...&id=...&canbus=...&signals=1789,1790&resolution=1000` returns:

```json
{"Count": 2, "Signals": [1789,1790], "Points": [
  {"Ordinal": 10, "Timestamp": 30674.1, "Signals": {"1789": 3.5, "1790": 0}},
  {"Ordinal": 11, "Timestamp": 30674.11, "Signals": {"1789": 3.6, "1790": 0}}
], "GeneralReturn": {"Error": 0}}
```

This example illustrates the verified shape; actual captured vendor records are in `tests/fixtures/plotpro.json`. Native dispatch/disassembly and simulation probes established that `resolution` is retained record capacity, not client decimation. **The response is generated before the requested subscription/capacity update.** The first response can contain a previous session's data; it primes the cursor. Subsequent requests return overlapping windows. Increasing ordinals identify new records; timestamps are the server's clock, not request arrival times. The tested server recorded roughly 100 points/s; repeated values are still preserved.

The client rejects malformed/nonmonotonic records atomically, deduplicates overlaps, counts missing ordinals on overruns and inserts graph/CSV gap records. Stream resets start a new epoch and break the curve. Selecting additional signals retains already captured data. Empty `signals` unsubscribes; vendor subscriptions also expire after inactivity. This is a shared vendor device stream, so competing Tuner instances can alter it: avoid concurrent plot clients.

All received records are transactionally spooled to temporary SQLite storage; rendering may downsample and retains at most 60,000 recent records. CSV streams the whole capture, including earlier selections and epochs. Storage failures stop acquisition with a visible error. Pause, Clear, device changes, disconnect and exit are explicit capture boundaries; export before clearing or leaving a device. A late response arriving after Pause is intentionally excluded.

“Lossless” is limited to retained server records. Native sampling, physical CAN signal freshness, bus saturation and server/firmware differences are not proven by simulation. A slow or disconnected client can overrun the 1,000-record server ring; this is reported, never concealed. Fetch interval does not change device signal frequency. `setupdatefrequency&signal=<single SPN>&frequencyhz=...` was probed successfully but is not automatically issued because it changes CAN traffic.

## Control requests

`getcontrols` returned 44 Talon FX request types in 26.3.0. It supplies `Summary`, `Description`, `RequiresCANivore`, `RequiresPro`, and `ConstructorParams`. Each parameter has `Name`, `Type`, optional `Default`, `Units`, `Min`, `Max`, `TunerMin`, `TunerMax`, or `EnumValues`. Do not infer a device supports a request based on another model's catalog. The editor covers advertised booleans, doubles, integers and enum values; unknown parameter types are rejected. Tuner-specific bounds are enforced in addition to SDK bounds.

Verified example:

```text
action=controlv2&controlmode=DutyCycleOut&controlen=true&Output=f_0.1&EnableFOC=b_False&...
```

Use parameter names exactly as advertised. Values carry native parser prefixes: `f_` for doubles, `i_` for signed integers/enums, `u_` for unsigned integers, `b_True` / `b_False` for booleans (case matters). Other constructor parameters must also be supplied. Disable uses `controlmode=NeutralOut&controlen=false`. Acknowledgment is not evidence of output: device enable, FRC lock, limits, licensing and configuration may inhibit it.

[CTRE's enable requirements](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/api-usage/enabling-actuators.html) still apply. Local SDK hosts feed `unmanaged.feed_enable(0.100)` only under an explicitly activated lease, renewed after successful control HTTP requests. IPC messages carry absolute monotonic deadlines, so delayed messages cannot renew an expired lease. Failed or stalled requests let that lease expire after 250 ms, followed by at most the last 100 ms SDK feed timeout. Disabling revokes the lease and sends neutral/disable. Network non-FRC applications supply enable in their own program.

**Robot program contention.** A robot program hosting the diagnostics server keeps its own control requests active (Phoenix 6 resends them at 100 Hz by default, even after a single `setControl`). Simulation probes showed each `controlv2` with `controlen=true` outranks those requests for only ~200 ms; the robot program then reclaims the device. Panther therefore resends every 40 ms on a dedicated connection and thread, independent of telemetry and GUI work, and logs any acknowledgment gap above 180 ms. Failed requests are retried while enabled instead of disabling control, so a busy roboRIO cannot silently end the session. With 200 ms of artificial latency on other requests, the former shared-queue 75 ms heartbeat produced ~223 ms gaps and lost the device to a 20 ms robot loop seven times in 3.8 s; the dedicated heartbeat kept 40 ms gaps and never lost it. Driver Station enable remains necessary on FRC-locked devices; Panther does not clear that lock.

Simulation verification: 0.1 DutyCycleOut produced approximately 0.099609 reported duty cycle and 1.23 V at 12.3 V supply. Output returned to zero after enable-lease expiry, after HTTP control heartbeat loss **while enable continued**, and after explicit Stop. The native request watchdog stopped output by 0.5 s in probes; its exact guarantee across server versions/hardware is unverified. Other control modes are schema-supported, not each electrically validated. Never rely on a desktop app as the sole emergency stop.

## Configuration schema

Each group has `Name`, `Summary`, `Description`, `Ordinal`, `Configs`. Each config includes `SignalId`, `SignalName`, `Name`, `Type`, `Value`, `DefaultValue`, `MinValue`, `MaxValue`, `Units`, `EnumValues`. Enums contain `Name`, `Value`, `Comment`.

All fields exposed by the server are rendered. Unexposed capabilities (for example bus/controller settings outside a device configuration schema) are not invented. Some nominal ranges exclude a legal disabling default: Control Timesync Freq has minimum 50 Hz, but default 0 disables it. Validation permits the server's exact default in addition to its range. Real devices quantize values: requesting duty-cycle deadband 0.012 returned 0.01171875. Exact readback differences are surfaced to the user.

## Configuration POST framing

Ordinary JSON POST and multipart/form-data **do not work** with the current server. Inspection of the official `libCTRE_PhoenixTools.so` showed a `$@$` delimiter, `X-Decoded-Size` header and base64 decoding. These were verified with a simulated device and an independent configuration refresh:

```python
data = json.dumps({"Device": groups, "JsonVersion": 2}, separators=(",", ":")).encode("utf-8")
body = b"$@$" + base64.b64encode(data) + b"$@$"
headers = {"Content-Type": "application/octet-stream", "X-Decoded-Size": str(len(data))}
# POST /?action=setconfigv2&model=<reported model>&id=<id>&canbus=<reported bus>
```

After a successful configuration POST, readback retries only vendor device-not-present (-102) or stale-frame (-1003) responses for at most one second. This accommodates an observed brief device-status interruption during simulator configuration updates. The POST itself is never repeated; HTTP timeouts, pre-write checks, and other vendor errors still fail immediately.

The server also supports `GET setconfigv2&file=<path on server>`, verified with a locally created file. The app uses the POST form so no remote filesystem access, SSH, or copying files to the roboRIO is needed. Blink and rename succeeded against simulation. ID changes returned a vendor error (-109); this is displayed, without claiming the device ID changed.

## Unsupported protocol areas

Firmware flashing, calibration, licensing, FRC lock changes and other unverified actions are not issued. Presence of a native string alone is not treated as proof of a usable protocol. Decorated HTML self-test templates are not executed: self-tests are native Qt tables, so vendor-supplied JavaScript is not run.

The legacy public diagnostics client documents a different upload format and old action names. It informed initial discovery research but was not treated as proof of current write behavior.
