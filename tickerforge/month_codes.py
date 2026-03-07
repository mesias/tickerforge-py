MONTH_TO_CODE: dict[int, str] = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

CODE_TO_MONTH: dict[str, int] = {code: month for month, code in MONTH_TO_CODE.items()}


def month_to_code(month: int) -> str:
    try:
        return MONTH_TO_CODE[month]
    except KeyError as exc:
        raise ValueError(f"Invalid month: {month}") from exc


def code_to_month(code: str) -> int:
    normalized = code.upper()
    try:
        return CODE_TO_MONTH[normalized]
    except KeyError as exc:
        raise ValueError(f"Invalid month code: {code}") from exc
