from __future__ import annotations

import copy
from typing import Any


class PathError(Exception):
    pass


def clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def deep_get(data: dict[str, Any], path: str) -> Any:
    # 容错：统一分隔符为 .，支持 / 和 . 两种格式
    path = path.replace("/", ".")
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            raise PathError(path)
    return current


def deep_exists(data: dict[str, Any], path: str) -> bool:
    try:
        deep_get(data, path)
        return True
    except PathError:
        return False


def deep_set(data: dict[str, Any], path: str, value: Any) -> None:
    # 容错：统一分隔符为 .，支持 / 和 . 两种格式
    path = path.replace("/", ".")
    parts = path.split(".")
    current: Any = data
    for key in parts[:-1]:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            raise PathError(path)
    last = parts[-1]
    if not isinstance(current, dict):
        raise PathError(path)
    current[last] = value


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_time(state: dict[str, Any], time_var: str = "time") -> None:
    if time_var not in state:
        return
    time_obj = state.get(time_var)
    if not isinstance(time_obj, dict):
        return
    if "minute" not in time_obj or "hour" not in time_obj:
        return

    minute = time_obj.get("minute", 0)
    hour = time_obj.get("hour", 0)
    day = time_obj.get("day", 1)

    if not is_number(minute) or not is_number(hour) or not is_number(day):
        return

    total_minutes = int(hour) * 60 + int(minute)
    if total_minutes < 0:
        total_minutes = 0
    hour = total_minutes // 60
    minute = total_minutes % 60

    time_obj["minute"] = int(minute)
    time_obj["hour"] = int(hour)
    time_obj["day"] = int(day)
