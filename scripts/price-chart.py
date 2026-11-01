import argparse
import colorsys
import math
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd

DEFAULT_START_YEAR = 2011
FORECAST_END_YEAR = 2029
POND_PRICE_COLUMNS = (
    'adult_payg_gbp',
    'concession_payg_gbp',
    'adult_season_12m_gbp',
    'concession_season_12m_gbp',
)
LIDO_PRICE_COLUMNS = (
    'adult_offpeak_payg_gbp',
    'concession_offpeak_payg_gbp',
    'adult_peak_payg_gbp',
    'concession_peak_payg_gbp',
    'adult_season_6m_gbp',
    'concession_season_6m_gbp',
    'adult_season_12m_gbp',
    'concession_season_12m_gbp',
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Plot Hampstead Heath bathing pond or Parliament Hill Lido ticket price trajectories.'
    )
    parser.add_argument(
        '--lido',
        action='store_true',
        help='Plot Parliament Hill Lido ticket prices (from prices/lido-fees.csv) instead of Bathing Ponds.',
    )
    parser.add_argument(
        '--combined',
        action='store_true',
        help='Plot a single combined dual-axis chart instead of separate sub-charts.',
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=DEFAULT_START_YEAR,
        help=f'Start year for the chart (default: {DEFAULT_START_YEAR}).',
    )
    parser.add_argument(
        '--geometric',
        '--geometric-2027',
        dest='geometric',
        action='store_true',
        help=(
            'Interpolate 2027 prices geometrically between 2026 and 2028 '
            '(equal annual percentage increase r_1 = sqrt(p_28 / p_26) - 1, '
            'rounded to £0.01).'
        ),
    )
    parser.add_argument(
        '--rpi',
        action='store_true',
        help='Plot RPI-adjusted lines for each ticket price series.',
    )
    parser.add_argument(
        '--cpih',
        action='store_true',
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
    parser.add_argument(
        '--core',
        action='store_true',
        help=(
            'Generate the four core charts (Bathing Ponds and Parliament Hill Lido '
            'from 2011 with RPI from 2020, for both linear and geometric 2027 prices).'
        ),
    )
    parser.add_argument(
        '-o',
        '--filename',
        '--output',
        dest='filename',
        type=str,
        default=None,
        help=(
            'Output PNG filename or path (default: auto-generated in charts/ '
            'from the active CLI options).'
        ),
    )
    return parser.parse_args(argv)


def build_default_filename(
    lido: bool,
    combined: bool,
    start_year: int,
    geometric: bool,
    show_rpi: bool,
    rpi_base_year: int,
    show_cpih: bool,
    cpih_base_year: int,
) -> str:
    prefix = 'lido_fees' if lido else 'ponds_fees'
    parts = [prefix]
    if combined:
        parts.append('combined')
    parts.append(f'from_{start_year}')
    if geometric:
        parts.append('geometric')
    if show_rpi:
        parts.append(f'rpi_{rpi_base_year}')
    if show_cpih:
        parts.append(f'cpih_{cpih_base_year}')
    return '_'.join(parts) + '.png'


def resolve_output_path(
    charts_dir: Path,
    filename: str | None,
    lido: bool,
    combined: bool,
    start_year: int,
    geometric: bool,
    show_rpi: bool,
    rpi_base_year: int,
    show_cpih: bool,
    cpih_base_year: int,
) -> Path:
    if not filename:
        return charts_dir / build_default_filename(
            lido=lido,
            combined=combined,
            start_year=start_year,
            geometric=geometric,
            show_rpi=show_rpi,
            rpi_base_year=rpi_base_year,
            show_cpih=show_cpih,
            cpih_base_year=cpih_base_year,
        )
    out_path = Path(filename)
    if not out_path.suffix:
        out_path = out_path.with_suffix('.png')
    if out_path.parent == Path('.'):
        return charts_dir / out_path
    return out_path


def apply_geometric_2027_interpolation(
    df: pd.DataFrame, price_columns: tuple[str, ...]
) -> pd.DataFrame:
    """Replace 2027 prices with the geometric mean of 2026 and 2028 (rounded to £0.01)."""
    result = df.copy()
    mask_26 = result['year'] == 2026
    mask_27 = result['year'] == 2027
    mask_28 = result['year'] == 2028
    for col in price_columns:
        p_26 = float(result.loc[mask_26, col].iloc[0])
        p_28 = float(result.loc[mask_28, col].iloc[0])
        r_2 = (p_28 / p_26) - 1.0
        r_1 = math.sqrt(r_2 + 1.0) - 1.0
        result.loc[mask_27, col] = round(p_26 * (1.0 + r_1), 2)
    return result


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


def month_timestamps_to_x(dates: pd.DatetimeIndex) -> pd.Index:
    return dates.year + (dates.month - 5) / 12.0


def compute_latest_annual_rate(index_monthly: pd.Series) -> float:
    latest_date = index_monthly.index.max()
    prev_year_date = latest_date - pd.DateOffset(years=1)
    if prev_year_date not in index_monthly.index:
        raise ValueError(f'No observation available 12 months before {latest_date:%Y-%m}')
    return float(index_monthly.loc[latest_date]) / float(index_monthly.loc[prev_year_date]) - 1.0


def desaturate_color(color: str, factor: float = 0.5) -> str:
    r, g, b = mcolors.to_rgb(color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return mcolors.to_hex(colorsys.hls_to_rgb(h, l, s * factor))


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


repo_root = Path(__file__).resolve().parent.parent
inflation_dir = repo_root / 'inflation'
rpi_monthly = load_monthly_index(inflation_dir / 'rpi.csv')
cpih_monthly = load_monthly_index(inflation_dir / 'cpih.csv')


def generate_chart(
    use_lido: bool,
    combined: bool,
    start_year: int,
    use_geometric: bool,
    show_rpi: bool,
    rpi_base_year: int,
    show_cpih: bool,
    cpih_base_year: int,
    filename: str | None = None,
) -> Path:
    show_inflation = show_rpi or show_cpih
    csv_name = 'lido-fees.csv' if use_lido else 'pond-fees.csv'
    price_columns = LIDO_PRICE_COLUMNS if use_lido else POND_PRICE_COLUMNS
    all_prices = pd.read_csv(repo_root / 'prices' / csv_name)
    if use_geometric:
        all_prices = apply_geometric_2027_interpolation(all_prices, price_columns)
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
    xtick_years = list(
        range(int(unique_years.iloc[0]), max(int(unique_years.iloc[-1]) + 1, FORECAST_END_YEAR) + 1)
    )

    def compute_inflation_series(
        price_col: str, index_monthly: pd.Series, base_year: int
    ) -> tuple[pd.Series, pd.Series, float]:
        base_date = pd.Timestamp(year=base_year, month=5, day=1)
        if base_date not in index_monthly.index:
            raise ValueError(f'No May inflation observation available for base year {base_year}')
        base_price = float(
            all_prices.loc[all_prices['year'] == base_year, price_col].iloc[0]
        )
        base_index = float(index_monthly.loc[base_date])
        filtered_monthly = index_monthly[index_monthly.index >= base_date]
        historical = base_price * filtered_monthly / base_index

        annual_rate = compute_latest_annual_rate(index_monthly)
        latest_date = index_monthly.index.max()
        latest_index = float(index_monthly.loc[latest_date])
        forecast_end_date = pd.Timestamp(year=FORECAST_END_YEAR, month=5, day=1)
        forecast_dates = pd.date_range(start=latest_date, end=forecast_end_date, freq='MS')
        forecast_indices = pd.Series(
            [
                latest_index * ((1.0 + annual_rate) ** (month_offset / 12.0))
                for month_offset in range(len(forecast_dates))
            ],
            index=forecast_dates,
        )
        forecast_indices = forecast_indices[forecast_indices.index >= base_date]
        forecast = base_price * forecast_indices / base_index
        return historical, forecast, annual_rate

    def plot_inflation_for_series(
        ax: plt.Axes,
        price_col: str,
        series_name: str,
        color: str,
        linestyle: str,
    ) -> list[plt.Line2D]:
        plotted: list[plt.Line2D] = []
        infl_color = desaturate_color(color, 0.5)
        for index_name, enabled, index_monthly, base_year in (
            ('RPI', show_rpi, rpi_monthly, rpi_base_year),
            ('CPIH', show_cpih, cpih_monthly, cpih_base_year),
        ):
            if not enabled:
                continue
            adjusted, forecast, annual_rate = compute_inflation_series(
                price_col, index_monthly, base_year
            )
            rate_pct = annual_rate * 100.0
            hist_lines = ax.plot(
                month_timestamps_to_x(adjusted.index),
                adjusted.values,
                color=infl_color,
                linestyle=linestyle,
                linewidth=2.0,
                alpha=0.5,
                label=f'{series_name} {index_name} ({base_year} base)',
            )
            forecast_lines = ax.plot(
                month_timestamps_to_x(forecast.index),
                forecast.values,
                color=infl_color,
                linestyle=':',
                linewidth=2.0,
                alpha=0.5,
                label=f'{series_name} {index_name} forecast ({rate_pct:+.1f}%/yr)',
            )
            plotted.extend(hist_lines)
            plotted.extend(forecast_lines)
        return plotted

    color_payg = '#1f77b4'
    color_payg_offpeak = '#2ca02c'
    color_season = '#d62728'
    facility_title = 'Parliament Hill Lido' if use_lido else 'Hampstead Heath Bathing Ponds'
    last_year = int(years.iloc[-1])
    penultimate_year = int(years.iloc[-2])
    active_indices = [
        name for name, enabled in (('RPI', show_rpi), ('CPIH', show_cpih)) if enabled
    ]
    inflation_title_suffix = f" with {' and '.join(active_indices)}" if active_indices else ''

    if combined:
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
        if use_lido:
            line_peak_a = ax1.plot(
                years, prices['adult_peak_payg_gbp'], marker='o', color=color_payg,
                linewidth=2.5, label='Adult Peak PAYG (£)',
            )
            line_peak_c = ax1.plot(
                years, prices['concession_peak_payg_gbp'], marker='s', linestyle='--',
                color=color_payg, linewidth=2, label='Concession Peak PAYG (£)',
            )
            line_off_a = ax1.plot(
                years, prices['adult_offpeak_payg_gbp'], marker='D', color=color_payg_offpeak,
                linewidth=2.5, label='Adult Off-Peak PAYG (£)',
            )
            line_off_c = ax1.plot(
                years, prices['concession_offpeak_payg_gbp'], marker='d', linestyle='--',
                color=color_payg_offpeak, linewidth=2, label='Concession Off-Peak PAYG (£)',
            )
            payg_primary_lines = line_peak_a + line_peak_c + line_off_a + line_off_c
            payg_inf_lines = (
                plot_inflation_for_series(ax1, 'adult_peak_payg_gbp', 'Adult Peak PAYG', color_payg, '-')
                + plot_inflation_for_series(ax1, 'concession_peak_payg_gbp', 'Concession Peak PAYG', color_payg, '--')
                + plot_inflation_for_series(ax1, 'adult_offpeak_payg_gbp', 'Adult Off-Peak PAYG', color_payg_offpeak, '-')
                + plot_inflation_for_series(ax1, 'concession_offpeak_payg_gbp', 'Concession Off-Peak PAYG', color_payg_offpeak, '--')
            )
            add_step_and_pct_labels(
                ax1, years, prices['adult_peak_payg_gbp'], color_payg, '-', 2.0,
                {penultimate_year: (5, 4, 'left'), last_year: (5, 0, 'left')},
            )
            add_step_and_pct_labels(
                ax1, years, prices['concession_peak_payg_gbp'], color_payg, '--', 1.8,
                {2012: (5, 4, 'left'), 2015: (5, 4, 'left'), 2017: (5, 4, 'left'), penultimate_year: (5, 6, 'left'), last_year: (5, 4, 'left')},
            )
            add_step_and_pct_labels(
                ax1, years, prices['adult_offpeak_payg_gbp'], color_payg_offpeak, '-', 2.0,
                {2015: (5, -4, 'left'), 2016: (5, 4, 'left'), 2017: (5, -4, 'left'), penultimate_year: (5, -6, 'left'), last_year: (5, 0, 'left')},
            )
            add_step_and_pct_labels(
                ax1, years, prices['concession_offpeak_payg_gbp'], color_payg_offpeak, '--', 1.8,
                {2015: (5, -4, 'left'), 2016: (5, -4, 'left'), 2017: (5, -4, 'left'), penultimate_year: (5, -4, 'left'), last_year: (5, -2, 'left')},
            )
            ax1.set_ylim(0.0, 15.0)
        else:
            line1 = ax1.plot(
                years, prices['adult_payg_gbp'], marker='o', color=color_payg,
                linewidth=2.5, label='Adult PAYG (£)',
            )
            line2 = ax1.plot(
                years, prices['concession_payg_gbp'], marker='s', linestyle='--',
                color=color_payg, linewidth=2, label='Concession PAYG (£)',
            )
            payg_primary_lines = line1 + line2
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
            ax1.set_ylim(0.0, 10.0)
        ax1.tick_params(axis='y', labelcolor=color_payg)
        ax1.grid(True, linestyle=':', alpha=0.6)
        ax1.set_xticks(xtick_years)
        ax1.set_xlim(xtick_years[0] - 0.5, xtick_years[-1] + 0.5)
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
            {2016: (5, 4, 'left'), 2017: (5, 4, 'left'), penultimate_year: (5, -4, 'left'), last_year: (5, 0, 'left')},
        )
        add_step_and_pct_labels(
            ax2, years, prices['concession_season_12m_gbp'], color_season, '--', 1.8,
            {2017: (5, -6, 'left'), 2021: (5, -8, 'left'), penultimate_year: (5, -4, 'left'), last_year: (5, 0, 'left')},
        )
        ax2.tick_params(axis='y', labelcolor=color_season)
        ax2.set_ylim(0.0, 440.0 if use_lido else 370.00)

        if use_lido:
            ax1.annotate(
                f'Adult Peak PAYG (£{prices["adult_peak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['adult_peak_payg_gbp'].iloc[-1]), xytext=(-12, 10),
                textcoords='offset points', ha='right', color=color_payg,
                arrowprops=dict(arrowstyle='->', color=color_payg),
            )
            ax1.annotate(
                f'Concession Peak PAYG (£{prices["concession_peak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['concession_peak_payg_gbp'].iloc[-1]), xytext=(-12, -24),
                textcoords='offset points', ha='right', color=color_payg,
                arrowprops=dict(arrowstyle='->', color=color_payg),
            )
            ax1.annotate(
                f'Adult Off-Peak PAYG (£{prices["adult_offpeak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['adult_offpeak_payg_gbp'].iloc[-1]), xytext=(-12, 12),
                textcoords='offset points', ha='right', color=color_payg_offpeak,
                arrowprops=dict(arrowstyle='->', color=color_payg_offpeak),
            )
            ax1.annotate(
                f'Concession Off-Peak PAYG (£{prices["concession_offpeak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['concession_offpeak_payg_gbp'].iloc[-1]), xytext=(-12, -22),
                textcoords='offset points', ha='right', color=color_payg_offpeak,
                arrowprops=dict(arrowstyle='->', color=color_payg_offpeak),
            )
        else:
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

        all_lines = payg_primary_lines + payg_inf_lines + line3 + line4 + season_inf_lines
        all_labels = [line.get_label() for line in all_lines]
        ax1.legend(
            all_lines, all_labels, loc='upper left', frameon=True,
            facecolor='white', edgecolor='#e2e2e2', handlelength=4.0,
        )

        plt.title(
            f'{facility_title}\nAnnual User Fee Trajectory'
            + inflation_title_suffix,
            fontweight='bold', fontsize=14, pad=15,
        )
    else:
        if use_lido:
            fig, (ax_season, ax_peak, ax_offpeak) = plt.subplots(
                3, 1, figsize=(14, 15), sharex=True
            )
        else:
            fig, (ax_season, ax_payg) = plt.subplots(
                2, 1, figsize=(14, 10), sharex=True
            )

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
            {2016: (6, 4, 'left'), 2017: (6, -6, 'left') if use_lido else (6, 4, 'left'), penultimate_year: (6, 12, 'left'), last_year: (6, 0, 'left')},
        )
        add_step_and_pct_labels(
            ax_season, years, prices['concession_season_12m_gbp'], color_season, '--', 1.8,
            {2017: (6, -6, 'left'), 2021: (6, -8, 'left'), penultimate_year: (6, -4, 'left'), last_year: (6, 0, 'left')},
        )
        ax_season.tick_params(axis='y', labelcolor=color_season)
        ax_season.tick_params(axis='x', labelbottom=True, rotation=45)
        ax_season.set_ylim(0.0, 440.0 if use_lido else 390.0)
        ax_season.grid(True, linestyle=':', alpha=0.6)
        ax_season.annotate(
            f'Adult 12M Season (£{prices["adult_season_12m_gbp"].iloc[-1]:.2f})',
            xy=(last_year, prices['adult_season_12m_gbp'].iloc[-1]), xytext=(-14, -5),
            textcoords='offset points', ha='right', va='center', color=color_season,
            arrowprops=dict(arrowstyle='->', color=color_season),
        )
        ax_season.annotate(
            f'Concession 12M Season (£{prices["concession_season_12m_gbp"].iloc[-1]:.2f})',
            xy=(last_year, prices['concession_season_12m_gbp'].iloc[-1]),
            xytext=(-14, -46) if use_lido else (-95, -45),
            textcoords='offset points', ha='right', va='center', color=color_season,
            arrowprops=dict(arrowstyle='->', color=color_season),
        )
        season_lines = line3 + line4 + season_inf_lines
        ax_season.legend(
            season_lines, [line.get_label() for line in season_lines],
            loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
            handlelength=4.0,
        )

        if use_lido:
            ax_peak.set_title(
                'Daily Peak PAYG Single Tickets' + inflation_title_suffix,
                fontweight='bold', fontsize=12, pad=10,
            )
            ax_peak.set_ylabel(
                'Peak PAYG Ticket / Inflation-Equivalent Price (£)' if show_inflation
                else 'Peak PAYG Ticket Price (£)',
                color=color_payg, fontweight='bold', labelpad=10,
            )
            line_peak_a = ax_peak.plot(
                years, prices['adult_peak_payg_gbp'], marker='o', color=color_payg,
                linewidth=2.5, label='Adult Peak PAYG (£)',
            )
            line_peak_c = ax_peak.plot(
                years, prices['concession_peak_payg_gbp'], marker='s', linestyle='--',
                color=color_payg, linewidth=2, label='Concession Peak PAYG (£)',
            )
            peak_inf_lines = (
                plot_inflation_for_series(ax_peak, 'adult_peak_payg_gbp', 'Adult Peak PAYG', color_payg, '-')
                + plot_inflation_for_series(ax_peak, 'concession_peak_payg_gbp', 'Concession Peak PAYG', color_payg, '--')
            )
            add_step_and_pct_labels(
                ax_peak, years, prices['adult_peak_payg_gbp'], color_payg, '-', 2.0,
                {penultimate_year: (6, 2, 'left'), last_year: (6, 0, 'left')},
            )
            add_step_and_pct_labels(
                ax_peak, years, prices['concession_peak_payg_gbp'], color_payg, '--', 1.8,
                {
                    2012: (6, -6, 'left'),
                    2015: (6, -6, 'left'),
                    2017: (6, -6, 'left'),
                    penultimate_year: (6, -4, 'left'),
                    last_year: (6, -2, 'left'),
                },
            )
            ax_peak.set_ylim(0.0, 15.0)
            ax_peak.tick_params(axis='y', labelcolor=color_payg)
            ax_peak.tick_params(axis='x', labelbottom=True, rotation=45)
            ax_peak.grid(True, linestyle=':', alpha=0.6)
            ax_peak.annotate(
                f'Adult Peak PAYG (£{prices["adult_peak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['adult_peak_payg_gbp'].iloc[-1]), xytext=(-14, 10),
                textcoords='offset points', ha='right', color=color_payg,
                arrowprops=dict(arrowstyle='->', color=color_payg),
            )
            ax_peak.annotate(
                f'Concession Peak PAYG (£{prices["concession_peak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['concession_peak_payg_gbp'].iloc[-1]), xytext=(-14, 14),
                textcoords='offset points', ha='right', color=color_payg,
                arrowprops=dict(arrowstyle='->', color=color_payg),
            )
            peak_lines = line_peak_a + line_peak_c + peak_inf_lines
            ax_peak.legend(
                peak_lines, [line.get_label() for line in peak_lines],
                loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
                handlelength=4.0,
            )

            ax_offpeak.set_title(
                'Daily Off-Peak PAYG Single Tickets' + inflation_title_suffix,
                fontweight='bold', fontsize=12, pad=10,
            )
            ax_offpeak.set_xlabel(
                'Year (May prices / index)' if show_inflation else 'Year (May prices)',
                fontweight='bold', labelpad=12,
            )
            ax_offpeak.set_ylabel(
                'Off-Peak PAYG Ticket / Inflation-Equivalent Price (£)' if show_inflation
                else 'Off-Peak PAYG Ticket Price (£)',
                color=color_payg_offpeak, fontweight='bold', labelpad=10,
            )
            line_off_a = ax_offpeak.plot(
                years, prices['adult_offpeak_payg_gbp'], marker='D', color=color_payg_offpeak,
                linewidth=2.5, label='Adult Off-Peak PAYG (£)',
            )
            line_off_c = ax_offpeak.plot(
                years, prices['concession_offpeak_payg_gbp'], marker='d', linestyle='--',
                color=color_payg_offpeak, linewidth=2, label='Concession Off-Peak PAYG (£)',
            )
            offpeak_inf_lines = (
                plot_inflation_for_series(ax_offpeak, 'adult_offpeak_payg_gbp', 'Adult Off-Peak PAYG', color_payg_offpeak, '-')
                + plot_inflation_for_series(ax_offpeak, 'concession_offpeak_payg_gbp', 'Concession Off-Peak PAYG', color_payg_offpeak, '--')
            )
            add_step_and_pct_labels(
                ax_offpeak, years, prices['adult_offpeak_payg_gbp'], color_payg_offpeak, '-', 2.0,
                {
                    2015: (6, 4, 'left'),
                    2016: (6, 2, 'left'),
                    2017: (6, -6, 'left'),
                    penultimate_year: (6, -2, 'left'),
                    last_year: (6, 0, 'left'),
                },
            )
            add_step_and_pct_labels(
                ax_offpeak, years, prices['concession_offpeak_payg_gbp'], color_payg_offpeak, '--', 1.8,
                {
                    2015: (6, -4, 'left'),
                    2016: (6, -4, 'left'),
                    2017: (6, -4, 'left'),
                    penultimate_year: (6, -4, 'left'),
                    last_year: (6, -2, 'left'),
                },
            )
            ax_offpeak.set_ylim(0.0, 9.0)
            ax_offpeak.tick_params(axis='y', labelcolor=color_payg_offpeak)
            ax_offpeak.grid(True, linestyle=':', alpha=0.6)
            ax_offpeak.set_xticks(xtick_years)
            ax_offpeak.set_xlim(xtick_years[0] - 0.5, xtick_years[-1] + 0.5)
            ax_offpeak.tick_params(axis='x', rotation=45)
            ax_offpeak.annotate(
                f'Adult Off-Peak PAYG (£{prices["adult_offpeak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['adult_offpeak_payg_gbp'].iloc[-1]), xytext=(-14, 12),
                textcoords='offset points', ha='right', color=color_payg_offpeak,
                arrowprops=dict(arrowstyle='->', color=color_payg_offpeak),
            )
            ax_offpeak.annotate(
                f'Concession Off-Peak PAYG (£{prices["concession_offpeak_payg_gbp"].iloc[-1]:.2f})',
                xy=(last_year, prices['concession_offpeak_payg_gbp'].iloc[-1]), xytext=(-14, 14),
                textcoords='offset points', ha='right', color=color_payg_offpeak,
                arrowprops=dict(arrowstyle='->', color=color_payg_offpeak),
            )
            offpeak_lines = line_off_a + line_off_c + offpeak_inf_lines
            ax_offpeak.legend(
                offpeak_lines, [line.get_label() for line in offpeak_lines],
                loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
                handlelength=4.0,
            )
        else:
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
            payg_primary_lines = line1 + line2
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
            ax_payg.set_ylim(0.0, 9.0)
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
            ax_payg.tick_params(axis='y', labelcolor=color_payg)
            ax_payg.grid(True, linestyle=':', alpha=0.6)
            ax_payg.set_xticks(xtick_years)
            ax_payg.set_xlim(xtick_years[0] - 0.5, xtick_years[-1] + 0.5)
            ax_payg.tick_params(axis='x', rotation=45)
            payg_lines = payg_primary_lines + payg_inf_lines
            ax_payg.legend(
                payg_lines, [line.get_label() for line in payg_lines],
                loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2',
                handlelength=4.0,
            )

        fig.suptitle(
            f'{facility_title} — User Fee Trajectory',
            fontweight='bold', fontsize=14, y=0.985 if use_lido else 0.98,
        )

    fig.tight_layout()

    charts_dir = repo_root / 'charts'
    charts_dir.mkdir(exist_ok=True)
    output_path = resolve_output_path(
        charts_dir=charts_dir,
        filename=filename,
        lido=use_lido,
        combined=combined,
        start_year=start_year,
        geometric=use_geometric,
        show_rpi=show_rpi,
        rpi_base_year=rpi_base_year,
        show_cpih=show_cpih,
        cpih_base_year=cpih_base_year,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f'Saved chart to {output_path}')
    return output_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.core:
        for use_geometric in (False, True):
            for use_lido in (False, True):
                generate_chart(
                    use_lido=use_lido,
                    combined=False,
                    start_year=2011,
                    use_geometric=use_geometric,
                    show_rpi=True,
                    rpi_base_year=2020,
                    show_cpih=False,
                    cpih_base_year=2020,
                    filename=None,
                )
        return

    start_year = args.start_year
    default_base_year = args.base_year if args.base_year is not None else start_year
    rpi_base_year = args.rpi_base_year if args.rpi_base_year is not None else default_base_year
    cpih_base_year = args.cpih_base_year if args.cpih_base_year is not None else default_base_year
    generate_chart(
        use_lido=args.lido,
        combined=args.combined,
        start_year=start_year,
        use_geometric=args.geometric,
        show_rpi=args.rpi,
        rpi_base_year=rpi_base_year,
        show_cpih=args.cpih,
        cpih_base_year=cpih_base_year,
        filename=args.filename,
    )


if __name__ == '__main__':
    main()
