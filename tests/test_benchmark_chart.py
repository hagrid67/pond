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
    data = pd.DataFrame(rows, columns=[
        benchmark_chart.VENUE_COLUMN, benchmark_chart.ADULT_COLUMN,
        benchmark_chart.CONCESSION_COLUMN, benchmark_chart.WATER_TEMPERATURE_COLUMN,
    ])
    data['Months per year'] = '12'
    return data


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


@pytest.mark.parametrize('annual', [False, True])
def test_seasonal_labels_are_per_venue_on_shared_markers(annual: bool) -> None:
    data = annual_venues()
    data['Months per year'] = ['7', '12', '6', '6', '12']
    points, excluded = benchmark_chart.prepare_scatter_points(data, annual=annual)
    labels = [label['text'] for label in benchmark_chart.build_labels(points)]
    assert 'Pond A (7/12m)\nPond B' in labels
    assert 'Pool C (6/12m)' in labels
    assert excluded == (['Lake D (6/12m)', 'Lake E'] if annual else ['Lake D (6/12m)'])


@pytest.mark.parametrize(
    ('months', 'expected'),
    [('0', 'Venue (0/12m)'), ('6', 'Venue (6/12m)'),
     ('6.5', 'Venue (6.5/12m)'), ('11', 'Venue (11/12m)'), ('12', 'Venue')],
)
def test_venue_label_reflects_opening_months(months: str, expected: str) -> None:
    data = make_venues([('Venue', '£5', '£3', 'Unheated')])
    data['Months per year'] = months
    points, _ = benchmark_chart.prepare_scatter_points(data)
    assert points.loc[0, 'venues'] == [expected]


@pytest.mark.parametrize('months', ['-1', '13', 'not a number', 'nan', 'inf'])
def test_invalid_opening_months_are_reported(months: str) -> None:
    data = make_venues([('Venue', '£5', '£3', 'Unheated')])
    data['Months per year'] = months
    with pytest.raises(ValueError, match='Venue.*Months per year'):
        benchmark_chart.prepare_scatter_points(data)


def test_missing_opening_months_warn_without_implying_a_season() -> None:
    data = make_venues([('Venue', '£5', '£3', 'Unheated')])
    data['Months per year'] = ''
    with pytest.warns(RuntimeWarning, match='Venue.*Months per year'):
        points, _ = benchmark_chart.prepare_scatter_points(data)
    assert points.loc[0, 'venues'] == ['Venue']


def test_merged_near_prices_keep_each_venue_opening_months() -> None:
    data = make_venues([
        ('Swiss', '£8.45', '£2.90', 'Heated'),
        ('Pancras', '£8.46', '£2.90', 'Heated'),
    ])
    data['Months per year'] = ['6', '12']
    points, _ = benchmark_chart.prepare_scatter_points(data)
    labels = benchmark_chart.build_labels(points)
    assert labels[0]['text'] == 'Swiss (6/12m) (£8.45)\nPancras (£8.46)'


def test_plot_benchmark_scatter_writes_png(tmp_path: Path) -> None:
    data = make_venues([
        ('Pond A', '£5.00', '£3.00', 'Unheated'),
        ('Pool B', '£7.00', '£4.00', 'Heated'),
        ('Lake C', '£9.00', '', 'Unheated'),
    ])
    points, excluded = benchmark_chart.prepare_scatter_points(data)
    output = benchmark_chart.plot_benchmark_scatter(points, excluded, tmp_path / 'chart.png', 'Sheet1')
    assert output.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'


def test_load_proposed_prices_linear_and_geometric() -> None:
    linear = benchmark_chart.load_proposed_prices().set_index(['facility', 'year'])
    geometric = benchmark_chart.load_proposed_prices(use_geometric=True).set_index(['facility', 'year'])
    ponds_2026, ponds_2028 = linear.loc[('Ponds', 2026)], linear.loc[('Ponds', 2028)]
    assert linear.loc[('Ponds', 2027), 'adult'] == pytest.approx((ponds_2026['adult'] + ponds_2028['adult']) / 2)
    assert geometric.loc[('Ponds', 2027), 'adult'] == pytest.approx(
        round((ponds_2026['adult'] * ponds_2028['adult']) ** 0.5, 2))
    assert geometric.loc[('Parliament Hill Lido', 2028)].equals(linear.loc[('Parliament Hill Lido', 2028)])


def test_plot_benchmark_scatter_with_proposed(tmp_path: Path) -> None:
    data = make_venues([('Pond A', '£5.00', '£3.00', 'Unheated')])
    points, excluded = benchmark_chart.prepare_scatter_points(data)
    proposed = benchmark_chart.load_proposed_prices()
    output = benchmark_chart.plot_benchmark_scatter(
        points, excluded, tmp_path / 'chart.png', 'Sheet1', proposed)
    assert output.stat().st_size > 0


def test_plot_rejects_non_string_proposal_facility(tmp_path: Path) -> None:
    data = make_venues([('Pond A', '£5.00', '£3.00', 'Unheated')])
    points, excluded = benchmark_chart.prepare_scatter_points(data)
    proposed = benchmark_chart.load_proposed_prices()
    proposed['facility'] = proposed['facility'].astype(object)
    proposed.loc[0, 'facility'] = 123
    fig, ax = benchmark_chart.plt.subplots(figsize=(14, 10))
    try:
        with patch.object(benchmark_chart.plt, 'subplots', return_value=(fig, ax)):
            with pytest.raises(ValueError, match='Invalid proposed facility 123'):
                benchmark_chart.plot_benchmark_scatter(
                    points, excluded, tmp_path / 'chart.png', 'Sheet1', proposed,
                )
    finally:
        benchmark_chart.plt.close(fig)


def annual_venues() -> pd.DataFrame:
    data = make_venues([
        ('Pond A', '£5.00', '£3.00', 'Unheated'),
        ('Pond B', '£5.00', '£3.00', 'Unheated'),
        ('Pool C', '£8.00', '£4.00', 'Heated'),
        ('Lake D', '£9.00', '', 'Unheated'),
        ('Lake E', '£10.00', '£5.00', 'Unheated'),
    ])
    data[benchmark_chart.ANNUAL_ADULT_COLUMN] = ['£157', '£157', '£504', '£400', '']
    data[benchmark_chart.ANNUAL_CONCESSION_COLUMN] = ['£94', '£94', '£352.80', '', '£200']
    return data


def heath_venues() -> pd.DataFrame:
    data = make_venues([
        ("Kenwood Ladies' Pond", '£5', '£3', 'Unheated'),
        ("Highgate Men's Pond", '£5', '£3', 'Unheated'),
        ('Hampstead Mixed Pond', '£5', '£3', 'Unheated'),
        ('Parliament Hill Lido', '£8.80', '£5.20', 'Unheated'),
    ])
    data['Months per year'] = ['12', '12', '7', '6']
    data[benchmark_chart.ANNUAL_ADULT_COLUMN] = ['£157', '£157', '£157', '£252']
    data[benchmark_chart.ANNUAL_CONCESSION_COLUMN] = ['£94', '£94', '£94', '£152']
    return data


def test_proposal_notes_identify_seasonal_venues_within_facility_groups() -> None:
    notes = benchmark_chart.build_proposed_opening_notes(heath_venues())
    assert notes == {
        'Ponds': 'Hampstead Mixed Pond (7/12m)',
        'Parliament Hill Lido': 'Parliament Hill Lido (6/12m)',
    }


def test_missing_proposed_venue_is_reported() -> None:
    data = heath_venues().iloc[:-1]
    with pytest.warns(RuntimeWarning, match='Parliament Hill Lido.*missing'):
        notes = benchmark_chart.build_proposed_opening_notes(data)
    assert notes['Ponds'] == 'Hampstead Mixed Pond (7/12m)'
    assert notes['Parliament Hill Lido'] == ''


@pytest.mark.parametrize('annual', [False, True])
def test_seasonal_venues_are_identified_on_proposed_price_labels(tmp_path: Path, annual: bool) -> None:
    data = heath_venues()
    points, excluded = benchmark_chart.prepare_scatter_points(data, annual=annual)
    proposed = benchmark_chart.load_proposed_prices(annual=annual)
    notes = benchmark_chart.build_proposed_opening_notes(data)
    fig, ax = benchmark_chart.plt.subplots(figsize=(14, 10))
    with patch.object(benchmark_chart.plt, 'subplots', return_value=(fig, ax)):
        benchmark_chart.plot_benchmark_scatter(
            points, excluded, tmp_path / 'chart.png', 'Sheet1',
            proposed, annual=annual, proposal_notes=notes,
        )
    labels = [text.get_text() for text in ax.texts if 'proposed' in text.get_text()]
    ponds = [label for label in labels if label.startswith('Ponds ')]
    lido = [label for label in labels if label.startswith('Parliament Hill Lido ')]
    assert len(ponds) == len(lido) == 2
    assert all('Hampstead Mixed Pond (7/12m)' in label for label in ponds)
    assert all('Parliament Hill Lido (6/12m)' in label for label in lido)
    assert all("Kenwood Ladies' Pond" not in label for label in ponds)


def test_prepare_annual_scatter_points() -> None:
    points, excluded = benchmark_chart.prepare_scatter_points(annual_venues(), annual=True)
    assert excluded == ['Lake D', 'Lake E']
    assert points.to_dict('records') == [
        {'adult': 157.0, 'concession': 94.0, 'heating': 'Unheated', 'venues': ['Pond A', 'Pond B']},
        {'adult': 504.0, 'concession': 352.8, 'heating': 'Heated', 'venues': ['Pool C']},
    ]


@pytest.mark.parametrize('use_geometric', [False, True])
def test_load_proposed_annual_prices(use_geometric: bool) -> None:
    prices = benchmark_chart.load_proposed_prices(use_geometric, annual=True)
    assert len(prices) == 6
    prices = prices.set_index(['facility', 'year'])
    endpoints = {
        'Ponds': ((157.0, 94.0), (360.0, 180.0)),
        'Parliament Hill Lido': ((252.0, 152.0), (405.0, 202.5)),
    }
    for facility, (current, future) in endpoints.items():
        assert prices.loc[(facility, 2026), ['adult', 'concession']].tolist() == list(current)
        assert prices.loc[(facility, 2028), ['adult', 'concession']].tolist() == list(future)
        expected = [
            round((start * end) ** 0.5, 2) if use_geometric else (start + end) / 2
            for start, end in zip(current, future)
        ]
        assert prices.loc[(facility, 2027), ['adult', 'concession']].tolist() == pytest.approx(expected)


def test_plot_annual_scatter_with_proposed(tmp_path: Path) -> None:
    points, excluded = benchmark_chart.prepare_scatter_points(annual_venues(), annual=True)
    proposed = benchmark_chart.load_proposed_prices(annual=True)
    fig, ax = benchmark_chart.plt.subplots(figsize=(14, 10))
    with patch.object(benchmark_chart.plt, 'subplots', return_value=(fig, ax)):
        output = benchmark_chart.plot_benchmark_scatter(
            points, excluded, tmp_path / 'annual.png', 'Sheet1', proposed, annual=True,
        )
    assert output.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    assert ax.get_xlabel() == 'Adult annual price (£)'
    assert ax.get_ylabel() == 'Concession annual price (£)'
    ticks = ax.get_xticks()
    assert (ticks[1:] - ticks[:-1]).tolist() == pytest.approx([100] * (len(ticks) - 1))
    assert len([text for text in ax.texts if 'proposed' in text.get_text()]) == 4
    reference_lines = [line for line in ax.lines if line.get_label().startswith('Concession =')]
    assert len(reference_lines) == 3
    for line, ratio in zip(reference_lines, (1.0, 0.5, 0.25)):
        assert list(line.get_ydata()) == pytest.approx([ratio * x for x in line.get_xdata()])
        assert line.get_linestyle() == '--'
        assert line.get_alpha() == 0.5
    footnote = fig.texts[0].get_text()
    assert 'missing annual adult or concession price' in footnote
    assert '12-month season tickets' in footnote
    assert 'peak PAYG' not in footnote


@pytest.mark.parametrize('no_proposed', [False, True])
@pytest.mark.parametrize('use_geometric', [False, True])
def test_main_generates_one_off_and_annual_charts(
    tmp_path: Path, no_proposed: bool, use_geometric: bool,
) -> None:
    token = tmp_path / 'token.pkl'
    token.touch()
    one_off_output = tmp_path / 'one-off.png'
    annual_output = tmp_path / 'annual.png'
    args = [
        '--token', str(token), '-o', str(one_off_output), '--annual-output', str(annual_output),
    ]
    if use_geometric:
        args.append('--geometric')
    if no_proposed:
        args.append('--no-proposed')
    expected_notes = {'Ponds': 'Hampstead Mixed Pond (7/12m)', 'Parliament Hill Lido': ''}
    with (
        patch.object(benchmark_chart, 'authenticate'),
        patch.object(benchmark_chart, 'build'),
        patch.object(benchmark_chart, 'load_benchmark_table',
                     return_value=('Sheet1', annual_venues(), pd.DataFrame())),
        patch.object(benchmark_chart, 'build_proposed_opening_notes', return_value=expected_notes) as notes,
        patch.object(benchmark_chart, 'plot_benchmark_scatter') as plot,
    ):
        benchmark_chart.main(args)
    assert plot.call_count == 2
    one_off, annual = plot.call_args_list
    assert one_off.args[2] == one_off_output
    assert annual.args[2] == annual_output
    expected_proposal_notes = None if no_proposed else expected_notes
    assert one_off.kwargs == {'proposal_notes': expected_proposal_notes}
    assert annual.kwargs == {'annual': True, 'proposal_notes': expected_proposal_notes}
    if no_proposed:
        notes.assert_not_called()
    else:
        notes.assert_called_once()
    for call in (one_off, annual):
        assert call.args[5] is use_geometric
        if no_proposed:
            assert call.args[4] is None
        else:
            assert len(call.args[4]) == 6
    assert annual.args[0]['adult'].tolist() == [157.0, 504.0]


def test_main_rejects_overwriting_one_off_with_annual(tmp_path: Path) -> None:
    output = str(tmp_path / 'chart.png')
    with pytest.raises(SystemExit) as exc:
        benchmark_chart.main(['-o', output, '--annual-output', output])
    assert exc.value.code == 2


def test_annual_labels_do_not_overlap_at_shared_heated_and_unheated_prices(tmp_path: Path) -> None:
    rows = [
        (f'Heated shared-price venue {i:02}', '£504', '£352.80', 'Heated')
        for i in range(17)
    ] + [
        ('Unheated venue A', '£504', '£352.80', 'Unheated'),
        ('Unheated venue B', '£504', '£352.80', 'Unheated'),
        ('Hampton Pool', '£681.40', '£492', 'Heated'),
        ('Sea Lanes', '£540', '£415.80', 'Unheated'),
        ('Brockwell', '£540', '£378', 'Unheated'),
        ('Greenland Dock', '£394.90', '£276', 'Unheated'),
        ('Tooting Bec', '£380', '£266', 'Unheated'),
        ('Aquatics Centre', '£429.90', '£300', 'Heated'),
        ('Ponds', '£157', '£94', 'Unheated'),
        ('Parliament Hill Lido', '£252', '£152', 'Unheated'),
        ('DWSC', '£150', '£105', 'Unheated'),
    ]
    data = pd.DataFrame(rows, columns=[
        benchmark_chart.VENUE_COLUMN, benchmark_chart.ANNUAL_ADULT_COLUMN,
        benchmark_chart.ANNUAL_CONCESSION_COLUMN, benchmark_chart.WATER_TEMPERATURE_COLUMN,
    ])
    data['Months per year'] = '12'
    points, excluded = benchmark_chart.prepare_scatter_points(data, annual=True)
    fig, ax = benchmark_chart.plt.subplots(figsize=(14, 10))
    try:
        with (
            patch.object(benchmark_chart.plt, 'subplots', return_value=(fig, ax)),
            patch.object(benchmark_chart.plt, 'close'),
        ):
            benchmark_chart.plot_benchmark_scatter(
                points, excluded, tmp_path / 'annual.png', 'Sheet1',
                benchmark_chart.load_proposed_prices(annual=True), annual=True,
            )
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        labels = [text for text in ax.texts if text.get_text()]
        for index, first in enumerate(labels):
            for second in labels[index + 1:]:
                assert not first.get_window_extent(renderer).overlaps(second.get_window_extent(renderer))
    finally:
        benchmark_chart.plt.close(fig)
