#%%

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

START_YEAR = 2011
SHOW_RPI = False
SHOW_CPIH = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Plot Hampstead Heath bathing pond ticket price trajectories.'
    )
    parser.add_argument(
        '--combined',
        action='store_true',
        help='Plot the original single combined dual-axis chart instead of two sub-charts.',
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=START_YEAR,
        help=f'Start year for the chart (default: {START_YEAR}).',
    )
    parser.add_argument(
        '--rpi',
        action='store_true',
        default=SHOW_RPI,
        help='Plot RPI-adjusted lines for each ticket price series.',
    )
    parser.add_argument(
        '--cpih',
        action='store_true',
        default=SHOW_CPIH,
        help='Plot CPIH-adjusted lines for each ticket price series.',
    )
    parser.add_argument(
        '--base-year',
        type=int,
        default=None,
        help='Base year at which RPI and CPIH lines pass through the ticket price (default: start year).',
    )
    parser.add_argument(
        '--rpi-base-year',
        type=int,
        default=None,
        help='Base year specifically for RPI lines (overrides --base-year).',
    )
    parser.add_argument(
        '--cpih-base-year',
        type=int,
        default=None,
        help='Base year specifically for CPIH lines (overrides --base-year).',
    )
    args, _ = parser.parse_known_args(argv)
    return args


args = parse_args()
start_year = args.start_year
show_rpi = args.rpi
show_cpih = args.cpih
show_inflation = show_rpi or show_cpih
default_base_year = args.base_year if args.base_year is not None else start_year
rpi_base_year = args.rpi_base_year if args.rpi_base_year is not None else default_base_year
cpih_base_year = args.cpih_base_year if args.cpih_base_year is not None else default_base_year

repo_root = Path(__file__).resolve().parent.parent
all_prices = pd.read_csv(repo_root / 'prices' / 'pond-fees.csv')
for label, year_val in (
    ('start year', start_year),
    ('RPI base year', rpi_base_year),
    ('CPIH base year', cpih_base_year),
):
    if year_val not in all_prices['year'].values:
        raise ValueError(f'No ticket prices available for {label} {year_val}')
prices = all_prices.loc[all_prices['year'] >= start_year].copy()
years = prices['year'].astype(int)
unique_years = years.drop_duplicates()


def load_monthly_index(path: Path) -> pd.Series:
    observations = pd.read_csv(
        path, header=None, names=['period', 'value'], usecols=[0, 1],
        dtype=str, keep_default_na=False,
    )
    monthly = observations[
        observations['period'].str.fullmatch(r'\d{4} [A-Z]{3}', na=False)
    ].copy()
    monthly.index = pd.DatetimeIndex(
        pd.to_datetime(monthly['period'], format='%Y %b'), name='month'
    )
    return pd.to_numeric(monthly['value'], errors='raise')


inflation_dir = repo_root / 'inflation'
rpi_monthly = load_monthly_index(inflation_dir / 'rpi.csv')
cpih_monthly = load_monthly_index(inflation_dir / 'cpih.csv')
rpi_may = rpi_monthly[
    (rpi_monthly.index.month == 5) & (rpi_monthly.index.year >= start_year)
]
cpih_may = cpih_monthly[
    (cpih_monthly.index.month == 5) & (cpih_monthly.index.year >= start_year)
]


def compute_inflation_series(
    price_col: str, index_monthly: pd.Series, index_may_series: pd.Series, base_year: int
) -> pd.Series:
    base_date = pd.Timestamp(year=base_year, month=5, day=1)
    if base_date not in index_monthly.index:
        raise ValueError(f'No May inflation observation available for base year {base_year}')
    base_price = float(
        all_prices.loc[all_prices['year'] == base_year, price_col].iloc[0]
    )
    return base_price * index_may_series / float(index_monthly.loc[base_date])


def plot_inflation_for_series(
    ax: plt.Axes,
    price_col: str,
    series_name: str,
    color: str,
    linestyle: str,
) -> list[plt.Line2D]:
    plotted: list[plt.Line2D] = []
    for index_name, enabled, index_monthly, index_may_series, base_year, marker in (
        ('RPI', show_rpi, rpi_monthly, rpi_may, rpi_base_year, 'D'),
        ('CPIH', show_cpih, cpih_monthly, cpih_may, cpih_base_year, 'P'),
    ):
        adjusted = compute_inflation_series(
            price_col, index_monthly, index_may_series, base_year
        )
        lines = ax.plot(
            adjusted.index.year,
            adjusted.values,
            marker=marker,
            markersize=5,
            color=color,
            linestyle=linestyle,
            linewidth=2.0,
            alpha=0.5,
            label=f'{series_name} {index_name} ({base_year} base)',
            visible=enabled,
        )
        plotted.extend(lines)
    return plotted

def add_step_and_pct_labels(
    ax: plt.Axes,
    x_years: pd.Series,
    y_prices: pd.Series,
    color: str,
    linestyle: str,
    linewidth: float,
    pct_offsets: dict[int, tuple[float, float, str]],
    min_pct: float = 10.0,
) -> None:
    step_x = pd.concat(
        [x_years, pd.Series([int(x_years.iloc[-1]) + 1])], ignore_index=True
    )
    step_y = pd.concat(
        [y_prices, pd.Series([float(y_prices.iloc[-1])])], ignore_index=True
    )
    ax.step(
        step_x, step_y, where='post', color=color,
        linestyle=linestyle, linewidth=linewidth, alpha=0.4,
    )
    for idx in range(1, len(x_years)):
        year = int(x_years.iloc[idx])
        prev_price = float(y_prices.iloc[idx - 1])
        curr_price = float(y_prices.iloc[idx])
        pct = (curr_price - prev_price) / prev_price * 100.0
        if pct <= min_pct:
            continue
        pct_str = f'+{pct:.1f}%'.replace('.0%', '%')
        mid_y = (prev_price + curr_price) / 2.0
        dx, dy, ha = pct_offsets.get(year, (6, 0, 'left'))
        ax.annotate(
            pct_str,
            xy=(year, mid_y),
            xytext=(dx, dy),
            textcoords='offset points',
            ha=ha,
            va='center',
            fontsize=9,
            fontweight='bold',
            color=color,
        )
color_payg = '#1f77b4'
color_season = '#d62728'
last_year = int(years.iloc[-1])
penultimate_year = int(years.iloc[-2])
active_indices = [
    name for name, enabled in (('RPI', show_rpi), ('CPIH', show_cpih)) if enabled
]
inflation_title_suffix = f" with {' and '.join(active_indices)}" if active_indices else ''

if args.combined:
    fig, ax1 = plt.subplots(figsize=(14, 7))

    ax1.set_xlabel(
        'Year (May prices / index)' if show_inflation else 'Year (May prices)',
        fontweight='bold', labelpad=12,
    )
    ax1.set_ylabel(
        'PAYG Single Ticket / Inflation-Equivalent Price (£)' if show_inflation
        else 'PAYG Single Ticket Price (£)',
        color=color_payg, fontweight='bold', labelpad=8,
    )
    line1 = ax1.plot(
        years, prices['adult_payg_gbp'], marker='o', color=color_payg,
        linewidth=2.5, label='Adult PAYG (£)',
    )
    line2 = ax1.plot(
        years, prices['concession_payg_gbp'], marker='s', linestyle='--',
        color=color_payg, linewidth=2, label='Concession PAYG (£)',
    )
    payg_inf_lines = (
        plot_inflation_for_series(ax1, 'adult_payg_gbp', 'Adult PAYG', color_payg, '-')
        + plot_inflation_for_series(ax1, 'concession_payg_gbp', 'Concession PAYG', color_payg, '--')
    )
    add_step_and_pct_labels(
        ax1, years, prices['adult_payg_gbp'], color_payg, '-', 2.0,
        {2020: (5, 4, 'left'), penultimate_year: (5, -2, 'left'), last_year: (5, 0, 'left')},
    )
    add_step_and_pct_labels(
        ax1, years, prices['concession_payg_gbp'], color_payg, '--', 1.8,
        {2020: (5, -6, 'left'), penultimate_year: (5, -4, 'left'), last_year: (5, -2, 'left')},
    )
    ax1.tick_params(axis='y', labelcolor=color_payg)
    ax1.set_ylim(0.0, 10.0)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.set_xticks(unique_years)
    ax1.set_xlim(unique_years.iloc[0] - 0.5, unique_years.iloc[-1] + 1.3)
    ax1.tick_params(axis='x', rotation=45)

    ax2 = ax1.twinx()
    ax2.set_ylabel(
        '12-Month Season Ticket / Inflation-Equivalent Price (£)' if show_inflation
        else '12-Month Season Ticket Price (£)',
        color=color_season, fontweight='bold', labelpad=12,
    )
    line3 = ax2.plot(
        years, prices['adult_season_12m_gbp'], marker='^', color=color_season,
        linewidth=2.5, label='Adult 12M Season (£)',
    )
    line4 = ax2.plot(
        years, prices['concession_season_12m_gbp'], marker='v', linestyle='--',
        color=color_season, linewidth=2, label='Concession 12M Season (£)',
    )
    season_inf_lines = (
        plot_inflation_for_series(ax2, 'adult_season_12m_gbp', 'Adult 12M Season', color_season, '-')
        + plot_inflation_for_series(ax2, 'concession_season_12m_gbp', 'Concession 12M Season', color_season, '--')
    )
    add_step_and_pct_labels(
        ax2, years, prices['adult_season_12m_gbp'], color_season, '-', 2.0,
        {penultimate_year: (5, -4, 'left'), last_year: (5, 0, 'left')},
    )
    add_step_and_pct_labels(
        ax2, years, prices['concession_season_12m_gbp'], color_season, '--', 1.8,
        {2021: (5, -8, 'left'), penultimate_year: (5, -4, 'left'), last_year: (5, 0, 'left')},
    )
    ax2.tick_params(axis='y', labelcolor=color_season)
    ax2.set_ylim(0.0, 370.00)

    ax1.annotate(
        f'Adult PAYG (£{prices["adult_payg_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['adult_payg_gbp'].iloc[-1]), xytext=(-12, -58),
        textcoords='offset points', ha='right', color=color_payg,
        arrowprops=dict(arrowstyle='->', color=color_payg),
    )
    ax1.annotate(
        f'Concession PAYG (£{prices["concession_payg_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['concession_payg_gbp'].iloc[-1]), xytext=(-12, -26),
        textcoords='offset points', ha='right', color=color_payg,
        arrowprops=dict(arrowstyle='->', color=color_payg),
    )
    ax2.annotate(
        f'Adult 12M Season (£{prices["adult_season_12m_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['adult_season_12m_gbp'].iloc[-1]), xytext=(-12, 35),
        textcoords='offset points', ha='right', color=color_season,
        arrowprops=dict(arrowstyle='->', color=color_season),
    )
    ax2.annotate(
        f'Concession 12M Season (£{prices["concession_season_12m_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['concession_season_12m_gbp'].iloc[-1]), xytext=(-12, 26),
        textcoords='offset points', ha='right', color=color_season,
        arrowprops=dict(arrowstyle='->', color=color_season),
    )

    all_lines = line1 + line2 + payg_inf_lines + line3 + line4 + season_inf_lines
    all_lines = [line for line in all_lines if line.get_visible()]
    all_labels = [line.get_label() for line in all_lines]
    ax1.legend(
        all_lines, all_labels, loc='upper left', frameon=True,
        facecolor='white', edgecolor='#e2e2e2',
    )

    plt.title(
        'Hampstead Heath Bathing Ponds\nAnnual User Fee Trajectory'
        + inflation_title_suffix,
        fontweight='bold', fontsize=14, pad=15,
    )
else:
    fig, (ax_season, ax_payg) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    ax1, ax2 = ax_season, ax_payg

    ax_season.set_title(
        '12-Month Season Tickets' + inflation_title_suffix,
        fontweight='bold', fontsize=12, pad=10,
    )
    ax_season.set_ylabel(
        '12-Month Season Ticket / Inflation-Equivalent Price (£)' if show_inflation
        else '12-Month Season Ticket Price (£)',
        color=color_season, fontweight='bold', labelpad=10,
    )
    line3 = ax_season.plot(
        years, prices['adult_season_12m_gbp'], marker='^', color=color_season,
        linewidth=2.5, label='Adult 12M Season (£)',
    )
    line4 = ax_season.plot(
        years, prices['concession_season_12m_gbp'], marker='v', linestyle='--',
        color=color_season, linewidth=2, label='Concession 12M Season (£)',
    )
    season_inf_lines = (
        plot_inflation_for_series(ax_season, 'adult_season_12m_gbp', 'Adult 12M Season', color_season, '-')
        + plot_inflation_for_series(ax_season, 'concession_season_12m_gbp', 'Concession 12M Season', color_season, '--')
    )
    add_step_and_pct_labels(
        ax_season, years, prices['adult_season_12m_gbp'], color_season, '-', 2.0,
        {penultimate_year: (6, 12, 'left'), last_year: (6, 0, 'left')},
    )
    add_step_and_pct_labels(
        ax_season, years, prices['concession_season_12m_gbp'], color_season, '--', 1.8,
        {2021: (6, -8, 'left'), penultimate_year: (6, -4, 'left'), last_year: (6, 0, 'left')},
    )
    ax_season.tick_params(axis='y', labelcolor=color_season)
    ax_season.tick_params(axis='x', labelbottom=True, rotation=45)
    ax_season.set_ylim(0.0, 390.0)
    ax_season.grid(True, linestyle=':', alpha=0.6)
    ax_season.annotate(
        f'Adult 12M Season (£{prices["adult_season_12m_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['adult_season_12m_gbp'].iloc[-1]), xytext=(-14, -5),
        textcoords='offset points', ha='right', va='center', color=color_season,
        arrowprops=dict(arrowstyle='->', color=color_season),
    )
    ax_season.annotate(
        f'Concession 12M Season (£{prices["concession_season_12m_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['concession_season_12m_gbp'].iloc[-1]), xytext=(-95, -45),
        textcoords='offset points', ha='right', va='center', color=color_season,
        arrowprops=dict(arrowstyle='->', color=color_season),
    )
    season_lines = [line for line in (line3 + line4 + season_inf_lines) if line.get_visible()]
    ax_season.legend(
        season_lines, [line.get_label() for line in season_lines],
        loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
    )

    ax_payg.set_title(
        'Daily PAYG Single Tickets' + inflation_title_suffix,
        fontweight='bold', fontsize=12, pad=10,
    )
    ax_payg.set_xlabel(
        'Year (May prices / index)' if show_inflation else 'Year (May prices)',
        fontweight='bold', labelpad=12,
    )
    ax_payg.set_ylabel(
        'PAYG Single Ticket / Inflation-Equivalent Price (£)' if show_inflation
        else 'PAYG Single Ticket Price (£)',
        color=color_payg, fontweight='bold', labelpad=10,
    )
    line1 = ax_payg.plot(
        years, prices['adult_payg_gbp'], marker='o', color=color_payg,
        linewidth=2.5, label='Adult PAYG (£)',
    )
    line2 = ax_payg.plot(
        years, prices['concession_payg_gbp'], marker='s', linestyle='--',
        color=color_payg, linewidth=2, label='Concession PAYG (£)',
    )
    payg_inf_lines = (
        plot_inflation_for_series(ax_payg, 'adult_payg_gbp', 'Adult PAYG', color_payg, '-')
        + plot_inflation_for_series(ax_payg, 'concession_payg_gbp', 'Concession PAYG', color_payg, '--')
    )
    add_step_and_pct_labels(
        ax_payg, years, prices['adult_payg_gbp'], color_payg, '-', 2.0,
        {2020: (6, 4, 'left'), penultimate_year: (6, -2, 'left'), last_year: (6, 0, 'left')},
    )
    add_step_and_pct_labels(
        ax_payg, years, prices['concession_payg_gbp'], color_payg, '--', 1.8,
        {2020: (6, -6, 'left'), penultimate_year: (6, -4, 'left'), last_year: (6, -2, 'left')},
    )
    ax_payg.tick_params(axis='y', labelcolor=color_payg)
    ax_payg.set_ylim(0.0, 9.0)
    ax_payg.grid(True, linestyle=':', alpha=0.6)
    ax_payg.set_xticks(unique_years)
    ax_payg.set_xlim(unique_years.iloc[0] - 0.5, unique_years.iloc[-1] + 1.3)
    ax_payg.tick_params(axis='x', rotation=45)
    ax_payg.annotate(
        f'Adult PAYG (£{prices["adult_payg_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['adult_payg_gbp'].iloc[-1]), xytext=(-14, 14),
        textcoords='offset points', ha='right', color=color_payg,
        arrowprops=dict(arrowstyle='->', color=color_payg),
    )
    ax_payg.annotate(
        f'Concession PAYG (£{prices["concession_payg_gbp"].iloc[-1]:.2f})',
        xy=(last_year, prices['concession_payg_gbp'].iloc[-1]), xytext=(-14, 16),
        textcoords='offset points', ha='right', color=color_payg,
        arrowprops=dict(arrowstyle='->', color=color_payg),
    )
    payg_lines = [line for line in (line1 + line2 + payg_inf_lines) if line.get_visible()]
    ax_payg.legend(
        payg_lines, [line.get_label() for line in payg_lines],
        loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
    )

    fig.suptitle(
        'Hampstead Heath Bathing Ponds — User Fee Trajectory',
        fontweight='bold', fontsize=14, y=0.98,
    )

fig.tight_layout()

charts_dir = repo_root / 'charts'
charts_dir.mkdir(exist_ok=True)
plt.savefig(charts_dir / 'bathing_ponds_fee_trajectory.png', dpi=300)
plt.show()

# %%
