"""Validate server-advertised control requests and encode CTRE's typed query values."""

import math

from .models import TunerError


def encode_control(catalog: dict, mode: str, values: dict) -> dict:
    if mode not in catalog:
        raise TunerError("This server does not advertise that control request")
    fields = catalog[mode].get("ConstructorParams", [])
    names = {f["Name"] for f in fields}
    if set(values) != names:
        raise TunerError("Supply exactly the parameters advertised by the device")
    encoded = {}
    for field in fields:
        name, kind = field["Name"], field["Type"]
        value = values[name]
        if kind == "bool":
            if type(value) is not bool:
                raise TunerError(f"{name} requires a boolean")
            encoded[name] = "b_True" if value else "b_False"
            continue
        try:
            number = float(value)
        except (TypeError, ValueError) as e:
            raise TunerError(f"{name} requires a number") from e
        if not math.isfinite(number):
            raise TunerError(f"{name} requires a finite value")
        for key, comparison in [
            ("Min", lambda n, v: n < v),
            ("Max", lambda n, v: n > v),
            ("TunerMin", lambda n, v: n < v),
            ("TunerMax", lambda n, v: n > v),
        ]:
            if key in field and comparison(number, float(field[key])):
                raise TunerError(f"{name} is outside {key} = {field[key]}")
        enums = field.get("EnumValues", [])
        if enums and number not in [float(e["Value"]) for e in enums]:
            raise TunerError(f"{name} requires a listed enum value")
        if kind == "double":
            encoded[name] = f"f_{number:.17g}"
        elif kind in ("int", "uint", "uint32_t") or enums:
            if not number.is_integer() or (kind != "int" and not enums and number < 0):
                raise TunerError(f"{name} requires an integer")
            encoded[name] = ("u_" if kind in ("uint", "uint32_t") else "i_") + str(int(number))
        else:
            raise TunerError(f"Unsupported control parameter type: {kind}")
    return encoded
