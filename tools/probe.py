"""Read-only, reproducible capture of a Phoenix Diagnostics Server."""

import argparse
import json
from pathlib import Path

from panther_tuner.backends.diagnostics import DiagnosticsBackend


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="172.22.11.2")
    p.add_argument("--port", type=int, default=1250)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    backend = DiagnosticsBackend(args.host, args.port)

    def save(name, result):
        (args.output / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    try:
        save("getversion", backend.connect())
        save("getdevices", backend.request("getdevices"))
        for index, device in enumerate(backend.discover()):
            for action in ["getsignals", "getconfigv2", "decoratedselftest", "deviceinformation"]:
                try:
                    save(f"{index}-{action}", backend.request(action, device))
                except Exception as error:
                    save(f"{index}-{action}-error", {"error": str(error)})
    finally:
        backend.close()


if __name__ == "__main__":
    main()
