import importlib.util
import pickle
from pathlib import Path
from unittest.mock import Mock, patch

import httplib2
import pandas as pd
import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'benchmark-chart.py'
spec = importlib.util.spec_from_file_location('benchmark_chart', SCRIPT)
assert spec is not None and spec.loader is not None
benchmark_chart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark_chart)


def test_authenticate_trusted_token(tmp_path: Path) -> None:
    token = tmp_path / 'token.pkl'
    with token.open('wb') as stream:
        pickle.dump(Credentials(token='test-token', scopes=benchmark_chart.SCOPES), stream)
    assert benchmark_chart.authenticate(token).valid


def test_authenticate_rejects_invalid_token(tmp_path: Path) -> None:
    token = tmp_path / 'token.pkl'
    with token.open('wb') as stream:
        pickle.dump(Credentials(token=None, scopes=benchmark_chart.SCOPES), stream)
    with pytest.raises(ValueError, match='Reauthorize'):
        benchmark_chart.authenticate(token)


def test_refresh_failure_preserves_token(tmp_path: Path) -> None:
    token = tmp_path / 'token.pkl'
    original = pickle.dumps(Credentials(
        token=None, refresh_token='test-refresh', token_uri='https://oauth2.googleapis.com/token',
        client_id='test-client', client_secret='test-secret', scopes=benchmark_chart.SCOPES,
    ))
    token.write_bytes(original)
    with patch.object(Credentials, 'refresh', side_effect=RefreshError('invalid_grant')):
        with pytest.raises(RuntimeError, match='--reauth'):
            benchmark_chart.authenticate(token)
    assert token.read_bytes() == original


def test_authenticate_rejects_missing_scopes(tmp_path: Path) -> None:
    token = tmp_path / 'token.pkl'
    with token.open('wb') as stream:
        pickle.dump(Credentials(
            token='test-token',
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
        ), stream)
    with pytest.raises(PermissionError, match='drive.metadata.readonly'):
        benchmark_chart.authenticate(token)


def test_list_recent_sheets_paginates_to_ten() -> None:
    service = Mock()
    files = service.files.return_value
    files.list.return_value.execute.side_effect = [
        {'files': [{'id': str(i)} for i in range(6)], 'nextPageToken': 'next'},
        {'files': [{'id': str(i)} for i in range(6, 10)]},
    ]
    assert len(benchmark_chart.list_recent_sheets(service)) == 10
    first, second = files.list.call_args_list
    assert first.kwargs['orderBy'] == 'modifiedTime desc'
    assert first.kwargs['pageSize'] == 10
    assert first.kwargs['q'] == (
        "mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    )
    assert second.kwargs['pageSize'] == 4
    assert second.kwargs['pageToken'] == 'next'


def test_print_nested_paths_and_urls(capsys: pytest.CaptureFixture[str]) -> None:
    service = Mock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {'files': [
        {'id': 'sheet1', 'name': 'Fees', 'parents': ['child'], 'modifiedTime': '2026-11-11',
         'webViewLink': 'https://docs.google.com/spreadsheets/d/sheet1/edit'},
        {'id': 'sheet2', 'name': 'Comparison', 'parents': ['child'], 'modifiedTime': '2026-11-10'},
        {'id': 'sheet3', 'name': 'Shared', 'modifiedTime': '2026-11-09'},
    ]}
    files.get.return_value.execute.side_effect = [
        {'id': 'my-root'},
        {'id': 'child', 'name': 'Benchmarks', 'parents': ['parent']},
        {'id': 'parent', 'name': 'Swimming', 'parents': ['my-root']},
    ]
    benchmark_chart.print_recent_sheets(service)
    output = capsys.readouterr().out
    assert output.count('Folder: My Drive/Swimming/Benchmarks') == 2
    assert 'https://docs.google.com/spreadsheets/d/sheet1/edit' in output
    assert 'https://docs.google.com/spreadsheets/d/sheet2/edit' in output
    assert 'no visible parent' in output
    assert files.get.call_count == 3


def test_unavailable_folder_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    service = Mock()
    files = service.files.return_value
    files.list.return_value.execute.return_value = {'files': [
        {'id': 'sheet', 'name': 'Fees', 'parents': ['hidden'], 'modifiedTime': '2026-11-11'},
    ]}
    files.get.return_value.execute.side_effect = [
        {'id': 'my-root'},
        HttpError(httplib2.Response({'status': '404'}), b'{}'),
    ]
    benchmark_chart.print_recent_sheets(service)
    output = capsys.readouterr()
    assert '[unavailable folder: hidden]' in output.out
    assert 'Warning: cannot read folder hidden (HTTP 404)' in output.err


def test_api_failure_is_not_hidden() -> None:
    service = Mock()
    service.files.return_value.list.return_value.execute.side_effect = HttpError(
        httplib2.Response({'status': '403'}), b'{}',
    )
    with pytest.raises(HttpError):
        benchmark_chart.print_recent_sheets(service)


SHEET_VALUES = [
    ['Swimming Facilities Benchmarking'],
    ['Comparative pricing (October 2026)'],
    [],
    ['Venue', 'Operator', 'Borough', 'Adult one-off (£)'],
    ['Lido A', 'Op A', 'Camden', '£8.80'],
    ['Pond B', 'Op B', 'Camden'],
    ['Average', '', '', '£6.90'],
    [],
    ['Data Sources & Research Notes'],
    ['Water Temperature Sources', 'Official portals', 'x', 'y'],
]


def test_extract_main_table_bounds_and_summary() -> None:
    data, summary = benchmark_chart.extract_main_table(SHEET_VALUES)
    assert list(data.columns) == ['Venue', 'Operator', 'Borough', 'Adult one-off (£)']
    assert data['Venue'].tolist() == ['Lido A', 'Pond B']
    assert data.loc[1, 'Adult one-off (£)'] == ''
    assert summary['Venue'].tolist() == ['Average']


def test_extract_main_table_requires_header() -> None:
    with pytest.raises(ValueError, match='No table header'):
        benchmark_chart.extract_main_table([['Title only'], []])


def test_print_benchmark_table_reads_first_sheet(capsys: pytest.CaptureFixture[str]) -> None:
    service = Mock()
    sheets = service.spreadsheets.return_value
    sheets.get.return_value.execute.return_value = {'sheets': [
        {'properties': {'title': "Bob's", 'index': 1}},
        {'properties': {'title': 'Sheet1', 'index': 0}},
    ]}
    sheets.values.return_value.get.return_value.execute.return_value = {'values': SHEET_VALUES}
    title, data, summary = benchmark_chart.load_benchmark_table(service)
    benchmark_chart.print_benchmark_table(title, data, summary, 2)
    assert len(data) == 2
    sheets.values.return_value.get.assert_called_once_with(
        spreadsheetId=benchmark_chart.BENCHMARK_SPREADSHEET_ID, range="'Sheet1'",
    )
    output = capsys.readouterr().out
    assert "Sheet 'Sheet1': 2 venues x 4 columns" in output
    assert 'Operator' in output and 'Borough' not in output
    assert 'Average' in output


def test_parse_gbp() -> None:
    assert benchmark_chart.parse_gbp('£8.80') == 8.8
    assert benchmark_chart.parse_gbp(' £1,050.00 ') == 1050.0
    assert benchmark_chart.parse_gbp('') is None


def test_classify_heating() -> None:
    assert benchmark_chart.classify_heating('Heated (29°C)') == 'Heated'
    assert benchmark_chart.classify_heating('Unheated - natural') == 'Unheated'
    with pytest.raises(ValueError, match='Cannot classify'):
        benchmark_chart.classify_heating('Ambient')


def make_venues(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=[
        benchmark_chart.VENUE_COLUMN, benchmark_chart.ADULT_COLUMN,
        benchmark_chart.CONCESSION_COLUMN, benchmark_chart.WATER_TEMPERATURE_COLUMN,
    ])


def test_prepare_scatter_points_groups_and_excludes() -> None:
    data = make_venues([
        ('Pond A', '£5.00', '£3.00', 'Unheated'),
        ('Pond B', '£5.00', '£3.00', 'Unheated'),
        ('Pool C', '£5.00', '£3.00', 'Heated'),
        ('Lake D', '£9.00', '', 'Unheated'),
    ])
    points, excluded = benchmark_chart.prepare_scatter_points(data)
    assert excluded == ['Lake D']
    assert points[['heating', 'venues']].values.tolist() == [
        ['Unheated', ['Pond A', 'Pond B']], ['Heated', ['Pool C']],
    ]


def test_build_labels_merges_near_duplicates_with_prices() -> None:
    data = make_venues([
        ('Swiss', '£8.45', '£2.90', 'Heated'),
        ('Pancras', '£8.46', '£2.90', 'Heated'),
        ('Lido', '£8.46', '£2.90', 'Unheated'),
        ('Far', '£8.50', '£2.90', 'Heated'),
    ])
    points, _ = benchmark_chart.prepare_scatter_points(data)
    labels = {label['text']: label for label in benchmark_chart.build_labels(points)}
    assert set(labels) == {'Swiss (£8.45)\nPancras (£8.46)', 'Lido', 'Far'}
    assert labels['Swiss (£8.45)\nPancras (£8.46)']['x'] == pytest.approx(8.455)


def test_plot_benchmark_scatter_writes_png(tmp_path: Path) -> None:
    data = make_venues([
        ('Pond A', '£5.00', '£3.00', 'Unheated'),
        ('Pool B', '£7.00', '£4.00', 'Heated'),
        ('Lake C', '£9.00', '', 'Unheated'),
    ])
    points, excluded = benchmark_chart.prepare_scatter_points(data)
    output = benchmark_chart.plot_benchmark_scatter(points, excluded, tmp_path / 'chart.png', 'Sheet1')
    assert output.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
