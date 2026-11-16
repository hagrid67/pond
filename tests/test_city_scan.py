import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'city-scan.py'
spec = importlib.util.spec_from_file_location('city_scan', SCRIPT)
city_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(city_scan)


def test_agenda_items_flag_to_follow_items() -> None:
    page = '\n'.join([
        '   9.     ASSISTANT DIRECTOR\'S REPORT',
        '          Report of the Executive Director',
        '  10.     *HAMPSTEAD HEATH 2025/26 OUTTURN',
        '  11.     For Decision',
    ])
    assert city_scan.agenda_items([page]) == [
        (9, False, "ASSISTANT DIRECTOR'S REPORT"),
        (10, True, 'HAMPSTEAD HEATH 2025/26 OUTTURN'),
    ]
