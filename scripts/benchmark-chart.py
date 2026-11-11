#!/usr/bin/env python3
"""Plot the swimming facilities Benchmarking Google Sheet as a price scatter chart."""

import argparse
import importlib.util
import pickle
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text
from matplotlib.ticker import FuncFormatter, MultipleLocator
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOKEN_PATH = REPO_ROOT / 'secrets' / 'token-google.pkl'
DEFAULT_CREDENTIALS_PATH = REPO_ROOT.parent / 'personal-finance' / 'google' / 'credentials.json'
DEFAULT_OAUTH_PORT = 8765
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]
SHEET_MIME_TYPE = 'application/vnd.google-apps.spreadsheet'
# "Benchmarking - October 2026" in My Drive/Civic/HMPA/hmpa-2026-committee/SwimForum-2026
BENCHMARK_SPREADSHEET_ID = '1SR5Id3ycgpRa8hnkUqSWmwDhZ4G7IgGqSf71XBFHCqU'
MIN_HEADER_CELLS = 3
SUMMARY_ROW_LABELS = {'average'}
VENUE_COLUMN = 'Venue'
ADULT_COLUMN = 'Adult one-off (£)'
CONCESSION_COLUMN = 'Concession (£)'
WATER_TEMPERATURE_COLUMN = 'Water Temperature'
HEATING_COLOURS = {'Heated': '#ff7f0e', 'Unheated': '#1f77b4'}
DEFAULT_OUTPUT_PATH = REPO_ROOT / 'charts' / 'benchmark1.png'
NEAR_PRICE_TOLERANCE = 0.02
CURRENT_YEAR = 2026
PROPOSED_YEARS = (2027, 2028)
ARROW_SAMPLES = 12
# (facility, use_lido, adult column, concession column, heating) in prices/*-fees.csv.
# The sheet's one-off prices match the ponds' PAYG and the lido's peak PAYG prices.
HEATH_FACILITIES = (
    ('Ponds', False, 'adult_payg_gbp', 'concession_payg_gbp', 'Unheated'),
    ('Parliament Hill Lido', True, 'adult_peak_payg_gbp', 'concession_peak_payg_gbp', 'Unheated'),
)


def load_price_chart_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location('price_chart', REPO_ROOT / 'scripts' / 'price-chart.py')
    if spec is None or spec.loader is None:
        raise ImportError('Cannot load scripts/price-chart.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_proposed_prices(use_geometric: bool = False) -> pd.DataFrame:
    """Return current and proposed Heath prices, one row per facility and year.

    2027 prices come from price-chart.py: linear mean of 2026 and 2028 by default, else geometric.
    """
    price_chart = load_price_chart_module()
    rows = []
    for facility, use_lido, adult_col, concession_col, heating in HEATH_FACILITIES:
        prices = price_chart.load_prices(use_lido, use_geometric).set_index('year')
        for year in (CURRENT_YEAR, *PROPOSED_YEARS):
            rows.append({
                'facility': facility, 'year': year, 'heating': heating,
                'adult': float(prices.loc[year, adult_col]),
                'concession': float(prices.loc[year, concession_col]),
            })
    return pd.DataFrame(rows)


def read_first_sheet_values(service: Resource, spreadsheet_id: str) -> tuple[str, list[list[str]]]:
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties(title,index)',
    ).execute()
    sheets = sorted(metadata.get('sheets', []), key=lambda s: s['properties'].get('index', 0))
    if not sheets:
        raise ValueError(f'Spreadsheet {spreadsheet_id} has no sheets.')
    title = sheets[0]['properties']['title']
    escaped_title = title.replace("'", "''")
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{escaped_title}'",
    ).execute()
    return title, response.get('values', [])


def extract_main_table(values: list[list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (data rows, summary rows) for the first block with a multi-column header.

    The table starts at the first row with at least MIN_HEADER_CELLS non-empty cells
    (skipping the title/subtitle rows) and ends at the next blank row.
    """
    def is_blank(row: list[str]) -> bool:
        return not any(str(cell).strip() for cell in row)

    header_index = next(
        (i for i, row in enumerate(values)
         if sum(bool(str(cell).strip()) for cell in row) >= MIN_HEADER_CELLS),
        None,
    )
    if header_index is None:
        raise ValueError('No table header found in the first sheet.')
    header = [str(cell).strip() for cell in values[header_index]]
    rows: list[list[str]] = []
    for row in values[header_index + 1:]:
        if is_blank(row):
            break
        rows.append((list(row) + [''] * len(header))[:len(header)])
    table = pd.DataFrame(rows, columns=header)
    is_summary = table.iloc[:, 0].str.strip().str.lower().isin(SUMMARY_ROW_LABELS)
    return table.loc[~is_summary].reset_index(drop=True), table.loc[is_summary].reset_index(drop=True)


def load_benchmark_table(service: Resource) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    title, values = read_first_sheet_values(service, BENCHMARK_SPREADSHEET_ID)
    data, summary = extract_main_table(values)
    return title, data, summary


def print_benchmark_table(
    title: str, data: pd.DataFrame, summary: pd.DataFrame, n_columns: int,
) -> None:
    columns = list(data.columns[:n_columns])
    print(f"Sheet '{title}': {len(data)} venues x {len(data.columns)} columns\n")
    print(pd.concat([data, summary], ignore_index=True)[columns].to_string(index=False))


def parse_gbp(value: str) -> float | None:
    cleaned = str(value).strip().replace('£', '').replace(',', '')
    return float(cleaned) if cleaned else None


def classify_heating(value: str) -> str:
    lowered = str(value).strip().lower()
    if lowered.startswith('unheated'):
        return 'Unheated'
    if lowered.startswith('heated'):
        return 'Heated'
    raise ValueError(f'Cannot classify water temperature {value!r} as heated or unheated.')


def prepare_scatter_points(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return one row per (adult, concession, heating) marker, and venues lacking prices.

    Venues with identical prices and heating share a marker and a multi-line label.
    """
    frame = pd.DataFrame({
        'venue': data[VENUE_COLUMN].str.strip(),
        'adult': data[ADULT_COLUMN].map(parse_gbp),
        'concession': data[CONCESSION_COLUMN].map(parse_gbp),
        'heating': data[WATER_TEMPERATURE_COLUMN].map(classify_heating),
    })
    missing = frame['adult'].isna() | frame['concession'].isna()
    excluded = frame.loc[missing, 'venue'].tolist()
    points = (
        frame.loc[~missing]
        .groupby(['adult', 'concession', 'heating'], as_index=False, sort=False)
        .agg(venues=('venue', list))
    )
    return points, excluded


def build_labels(points: pd.DataFrame, tolerance: float = NEAR_PRICE_TOLERANCE) -> list[dict[str, Any]]:
    """Merge labels of same-heating markers within `tolerance` (£) on both axes.

    Merged labels state each venue's exact adult price so the near-duplicates stay distinguishable.
    """
    labels: list[dict[str, Any]] = []
    for row in points.sort_values(['adult', 'concession']).itertuples():
        match = next(
            (label for label in labels
             if label['heating'] == row.heating
             and abs(label['x'] - row.adult) <= tolerance
             and abs(label['y'] - row.concession) <= tolerance),
            None,
        )
        if match is None:
            labels.append({'x': row.adult, 'y': row.concession, 'heating': row.heating,
                           'members': [(row.adult, row.venues)]})
        else:
            match['members'].append((row.adult, row.venues))
    for label in labels:
        prices_differ = len({adult for adult, _ in label['members']}) > 1
        lines = [
            f'{venue} (£{adult:.2f})' if prices_differ else venue
            for adult, venues in label['members'] for venue in venues
        ]
        label['text'] = '\n'.join(lines)
        label['x'] = sum(adult for adult, _ in label['members']) / len(label['members'])
    return labels


def plot_benchmark_scatter(
    points: pd.DataFrame, excluded: list[str], output_path: Path, sheet_title: str,
    proposed: pd.DataFrame | None = None, use_geometric: bool = False,
) -> Path:
    fig, ax = plt.subplots(figsize=(14, 10))
    for heating, colour in HEATING_COLOURS.items():
        subset = points.loc[points['heating'] == heating]
        ax.scatter(
            subset['adult'], subset['concession'],
            s=[60 + 30 * (len(v) - 1) for v in subset['venues']],
            color=colour, edgecolor='black', linewidth=0.6, alpha=0.9, zorder=3,
            label=f'{heating} ({sum(len(v) for v in subset["venues"])} venues)',
        )

    labels = build_labels(points)
    mean_name = 'geometric' if use_geometric else 'linear'
    all_x, all_y = points['adult'].tolist(), points['concession'].tolist()
    if proposed is not None and not proposed.empty:
        ax.scatter([], [], marker='D', s=60, facecolor='white', edgecolor='#555555', linewidth=1.8,
                   label=f'Proposed Heath prices (2027 = {mean_name} mean)')
        for facility, group in proposed.groupby('facility', sort=False):
            group = group.sort_values('year')
            colour = HEATING_COLOURS[group['heating'].iloc[0]]
            coords = list(zip(group['adult'], group['concession']))
            for start, end in zip(coords, coords[1:]):
                ax.annotate('', xy=end, xytext=start, zorder=2, arrowprops={
                    'arrowstyle': '->', 'color': colour, 'linestyle': '--',
                    'linewidth': 1.2, 'shrinkA': 6, 'shrinkB': 6,
                })
                # Sample the arrow so adjust_text keeps labels off it.
                for step in range(1, ARROW_SAMPLES):
                    frac = step / ARROW_SAMPLES
                    all_x.append(start[0] + frac * (end[0] - start[0]))
                    all_y.append(start[1] + frac * (end[1] - start[1]))
            future = group.loc[group['year'].isin(PROPOSED_YEARS)]
            ax.scatter(future['adult'], future['concession'], marker='D', s=60, facecolor='white',
                       edgecolor=colour, linewidth=1.8, zorder=3)
            for row in future.itertuples():
                suffix = f' ({mean_name})' if row.year == 2027 else ''
                labels.append({
                    'x': row.adult, 'y': row.concession, 'heating': row.heating,
                    'text': f'{facility} {row.year} proposed{suffix}\n£{row.adult:.2f} / £{row.concession:.2f}',
                })
            all_x += future['adult'].tolist()
            all_y += future['concession'].tolist()

    texts = [
        ax.text(label['x'], label['y'], label['text'], fontsize=8,
                color=HEATING_COLOURS[label['heating']], ha='center', va='center', zorder=4)
        for label in labels
    ]
    ax.set_xlabel(f'{ADULT_COLUMN}', fontweight='bold')
    ax.set_ylabel(f'{CONCESSION_COLUMN}', fontweight='bold')
    ax.set_title(
        'Swimming Facilities Benchmarking — Adult vs Concession one-off price',
        fontweight='bold', fontsize=14,
    )
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'£{v:.0f}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'£{v:.0f}'))
    ax.xaxis.set_major_locator(MultipleLocator(1))
    x_limits = (min(all_x) - 1.0, max(all_x) + 1.0)
    ax.set_xlim(*x_limits)
    ax.set_ylim(min(all_y) - 0.75, max(all_y) + 0.75)
    ax.plot(x_limits, x_limits, linestyle='--', color='grey', alpha=0.5, linewidth=1.2,
            zorder=1, label='Concession = Adult')
    ax.plot(x_limits, [0.5 * x for x in x_limits], linestyle='--', color='grey', alpha=0.5,
            linewidth=1.2, zorder=1, label='Concession = 50% of Adult')
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2')
    footnote = f"Source: Google Sheet '{sheet_title}' (Benchmarking - October 2026)."
    if excluded:
        footnote += f" Not plotted (no concession price): {', '.join(excluded)}."
    if proposed is not None and not proposed.empty:
        footnote += (
            f' Proposed Heath prices from prices/pond-fees.csv and lido-fees.csv (lido: peak PAYG);'
            f' 2027 is the {mean_name} mean of 2026 and 2028.'
        )
    fig.text(0.01, 0.01, footnote, fontsize=8, style='italic', color='#333333', wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    adjust_text(
        texts,
        target_x=[label['x'] for label in labels],
        target_y=[label['y'] for label in labels],
        x=all_x,
        y=all_y,
        ax=ax,
        ensure_inside_axes=True,
        expand=(1.2, 1.5),
        force_static=(0.3, 0.5),
        arrowprops={'arrowstyle': '-', 'color': '#888888', 'linewidth': 0.6},
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f'Saved chart to {output_path}')
    return output_path


def authorize_in_browser(
    credentials_path: Path, token_path: Path, port: int, open_browser: bool,
) -> Credentials:
    if not credentials_path.exists():
        raise FileNotFoundError(f'OAuth client secrets not found at {credentials_path}.')
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    credentials = flow.run_local_server(
        port=port,
        open_browser=open_browser,
        authorization_prompt_message='Open this URL in your browser to authorize:\n{url}\n',
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open('wb') as token_file:
        pickle.dump(credentials, token_file)
    print(f'Saved token to {token_path}\n')
    return credentials


def authenticate(token_path: Path) -> Credentials:
    # Pickle can execute code: only load a trusted, locally supplied token file.
    with token_path.open('rb') as token_file:
        credentials = pickle.load(token_file)
    if not isinstance(credentials, Credentials):
        raise TypeError(f'{token_path} must contain Google OAuth Credentials.')
    missing = set(SCOPES) - set(credentials.scopes or [])
    if missing:
        raise PermissionError(
            f'{token_path} lacks scopes {sorted(missing)}. Rerun with --reauth.'
        )
    if not credentials.valid:
        if not credentials.refresh_token:
            raise ValueError('Google token is invalid and has no refresh token. Reauthorize it.')
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise RuntimeError(
                f'Google rejected the token refresh for {token_path}. Rerun with --reauth.'
            ) from exc
        with token_path.open('wb') as token_file:
            pickle.dump(credentials, token_file)
    return credentials


def list_recent_sheets(service: Resource) -> list[dict[str, Any]]:
    sheets: list[dict[str, Any]] = []
    page_token = None
    while len(sheets) < 10:
        response = service.files().list(
            q=f"mimeType = '{SHEET_MIME_TYPE}' and trashed = false",
            spaces='drive',
            orderBy='modifiedTime desc',
            pageSize=10 - len(sheets),
            pageToken=page_token,
            fields='nextPageToken,files(id,name,parents,modifiedTime,webViewLink)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        sheets.extend(response.get('files', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return sheets


def print_recent_sheets(service: Resource) -> None:
    sheets = list_recent_sheets(service)
    if not sheets:
        print('No Google Sheets found.')
        return

    root = service.files().get(fileId='root', fields='id').execute()
    folder_paths = {root['id']: 'My Drive'}

    def folder_path(folder_id: str, ancestors: frozenset[str] = frozenset()) -> str:
        if folder_id in folder_paths:
            return folder_paths[folder_id]
        if folder_id in ancestors:
            raise ValueError(f'Cycle in Google Drive folder ancestry at {folder_id}')
        try:
            folder = service.files().get(
                fileId=folder_id,
                fields='id,name,parents',
                supportsAllDrives=True,
            ).execute()
        except HttpError as exc:
            if exc.resp.status not in (403, 404):
                raise
            print(
                f'Warning: cannot read folder {folder_id} (HTTP {exc.resp.status}).',
                file=sys.stderr,
            )
            path = f'[unavailable folder: {folder_id}]'
        else:
            parents = folder.get('parents', [])
            prefix = (
                folder_path(parents[0], ancestors | {folder_id}) + '/'
                if parents else ''
            )
            path = prefix + folder['name']
        folder_paths[folder_id] = path
        return path

    print(f'{len(sheets)} most recently modified Google Sheets:\n')
    for index, sheet in enumerate(sheets, 1):
        parents = sheet.get('parents', [])
        folders = (
            ' | '.join(folder_path(parent) for parent in parents)
            if parents else '[no visible parent; possibly shared with me]'
        )
        url = sheet.get('webViewLink') or f'https://docs.google.com/spreadsheets/d/{sheet["id"]}/edit'
        print(
            f'{index}. {sheet["name"]}\n'
            f'   Folder: {folders}\n'
            f'   Modified: {sheet["modifiedTime"]}\n'
            f'   URL: {url}\n'
            f'   ID: {sheet["id"]}\n'
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--token', type=Path, default=DEFAULT_TOKEN_PATH,
        help='Trusted pickled Google OAuth token (default: repository secrets/token-google.pkl).',
    )
    parser.add_argument(
        '--reauth', action='store_true',
        help='Sign in via the browser and overwrite the token file.',
    )
    parser.add_argument(
        '--credentials', type=Path, default=DEFAULT_CREDENTIALS_PATH,
        help='OAuth client secrets JSON (default: ../personal-finance/google/credentials.json, perfin project).',
    )
    parser.add_argument(
        '--port', type=int, default=DEFAULT_OAUTH_PORT,
        help=f'Local OAuth callback port (default: {DEFAULT_OAUTH_PORT}).',
    )
    parser.add_argument(
        '--no-browser', action='store_true',
        help='Print the authorization URL instead of launching a browser.',
    )
    parser.add_argument(
        '--list-sheets', action='store_true',
        help='Also list the ten most recently modified Google Sheets.',
    )
    parser.add_argument(
        '--columns', type=int, default=0,
        help='Also print this many leading benchmark table columns (default: 0, off).',
    )
    parser.add_argument(
        '-o', '--output', type=Path, default=DEFAULT_OUTPUT_PATH,
        help='Output PNG path (default: charts/benchmark1.png).',
    )
    parser.add_argument(
        '--geometric', action='store_true',
        help='Use the geometric (not linear) mean of 2026 and 2028 for proposed 2027 Heath prices.',
    )
    parser.add_argument(
        '--no-proposed', action='store_true',
        help='Do not plot proposed 2027/2028 pond and lido prices.',
    )
    args = parser.parse_args(argv)
    if args.reauth or not args.token.exists():
        credentials = authorize_in_browser(
            args.credentials, args.token, args.port, open_browser=not args.no_browser,
        )
    else:
        credentials = authenticate(args.token)
    if args.list_sheets:
        print_recent_sheets(build('drive', 'v3', credentials=credentials))
    title, data, summary = load_benchmark_table(build('sheets', 'v4', credentials=credentials))
    if args.columns > 0:
        print_benchmark_table(title, data, summary, args.columns)
    points, excluded = prepare_scatter_points(data)
    proposed = None if args.no_proposed else load_proposed_prices(args.geometric)
    plot_benchmark_scatter(points, excluded, args.output, title, proposed, args.geometric)


if __name__ == '__main__':
    main()
