from datetime import date
from pathlib import Path

from tickerforge import TickerForge


def test_generate_ind_front_contract_before_expiry():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))

    ticker = forge.generate("IND", date="2026-06-01")
    assert ticker == "INDM26"


def test_generate_ind_rolls_after_expiry():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))

    ticker = forge.generate("IND", date="2026-06-18")
    assert ticker == "INDQ26"


def test_gen_defaults_to_today():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))
    today = date.today()

    assert forge.gen("DOL") == forge.generate("DOL", date=today)
    assert forge.gen("DOL", offset=1) == forge.generate("DOL", date=today, offset=1)


def test_generate_dol_wdo_di1_rolls_on_last_business_day():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))

    # On July 30th (day before last business day), front month is August (Q)
    assert forge.generate("DOL", date="2026-07-30") == "DOLQ26"
    assert forge.generate("WDO", date="2026-07-30") == "WDOQ26"
    assert forge.generate("DI1", date="2026-07-30") == "DI1Q26"

    # On July 31st (last business day of July), rolls to September (U)
    assert forge.generate("DOL", date="2026-07-31") == "DOLU26"
    assert forge.generate("WDO", date="2026-07-31") == "WDOU26"
    assert forge.generate("DI1", date="2026-07-31") == "DI1U26"

    # On August 3rd (first business day of August), front month remains September (U)
    assert forge.generate("DOL", date="2026-08-03") == "DOLU26"
    assert forge.generate("WDO", date="2026-08-03") == "WDOU26"
    assert forge.generate("DI1", date="2026-08-03") == "DI1U26"

    # Negative offset on July 31st returns expiring August contract
    assert forge.generate("DOL", date="2026-07-31", offset=-1) == "DOLQ26"
    assert forge.generate("WDO", date="2026-07-31", offset=-1) == "WDOQ26"


def test_futures_resolve_csv_b3_all_rows():
    import csv

    spec_path = Path(__file__).resolve().parents[1] / "spec"
    csv_path = spec_path / "tests/b3/futures_resolve.csv"
    forge = TickerForge(spec_path=str(spec_path))

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row["symbol"]
            if sym == "ICF":
                continue
            d = row["date"]
            offset = int(row["offset"])
            expected = row["expected"]
            got = forge.generate(sym, date=d, offset=offset)
            assert got == expected, f"Failed for row: {row}"
