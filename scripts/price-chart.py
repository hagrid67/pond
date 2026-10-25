#%%

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

START_YEAR = 2011

repo_root = Path(__file__).resolve().parent.parent
prices = pd.read_csv(repo_root / 'prices' / 'pond-fees.csv')
if START_YEAR not in prices['year'].values:
    raise ValueError(f'No ticket prices available for start year {START_YEAR}')
prices = prices.loc[prices['year'] >= START_YEAR].copy()
years = prices['year'].astype(int)


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
    (rpi_monthly.index.month == 5) & (rpi_monthly.index.year >= START_YEAR)
]
cpih_may = cpih_monthly[
    (cpih_monthly.index.month == 5) & (cpih_monthly.index.year >= START_YEAR)
]
base_date = pd.Timestamp(year=START_YEAR, month=5, day=1)
adult_season_base = prices.loc[prices['year'] == START_YEAR, 'adult_season_12m_gbp'].iloc[0]
rpi_adjusted = adult_season_base * rpi_may / rpi_may.loc[base_date]
cpih_adjusted = adult_season_base * cpih_may / cpih_may.loc[base_date]

fig, ax1 = plt.subplots(figsize=(14, 7))

color_payg = '#1f77b4'
ax1.set_xlabel('Year (May prices / index)', fontweight='bold', labelpad=12)
ax1.set_ylabel('PAYG Single Ticket Price (£)', color=color_payg, fontweight='bold', labelpad=8)
line1 = ax1.plot(
    years, prices['adult_payg_gbp'], marker='o', color=color_payg,
    linewidth=2.5, label='Adult PAYG (£)',
)
line2 = ax1.plot(
    years, prices['concession_payg_gbp'], marker='s', linestyle='--',
    color=color_payg, linewidth=2, label='Concession PAYG (£)',
)
color_rpi = '#ff7f0e'
color_cpih = '#2ca02c'
ax1.tick_params(axis='y', labelcolor=color_payg)
ax1.set_ylim(0.0, 10.0)
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.set_xticks(years)
ax1.set_xlim(years.iloc[0] - 0.5, years.iloc[-1] + 0.5)
ax1.tick_params(axis='x', rotation=45)

ax2 = ax1.twinx()
color_season = '#d62728'
ax2.set_ylabel('12-Month Season Ticket / Inflation-Equivalent Price (£)', color=color_season, fontweight='bold', labelpad=12)
line3 = ax2.plot(
    years, prices['adult_season_12m_gbp'], marker='^', color=color_season,
    linewidth=2.5, label='Adult 12M Season (£)',
)
line4 = ax2.plot(
    years, prices['concession_season_12m_gbp'], marker='v', linestyle='--',
    color=color_season, linewidth=2, label='Concession 12M Season (£)',
)
line5 = ax2.plot(
    rpi_adjusted.index.year, rpi_adjusted.values, marker='D',
    color=color_rpi, linewidth=2.5, label='RPI-adjusted 12M Adult Season (£)',
)
line6 = ax2.plot(
    cpih_adjusted.index.year, cpih_adjusted.values, marker='P',
    color=color_cpih, linewidth=2.5, label='CPIH-adjusted 12M Adult Season (£)',
)
ax2.tick_params(axis='y', labelcolor=color_season)
ax2.set_ylim(0.0, 370.00)

last_year = int(years.iloc[-1])
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
for series, label, color, text_offset in (
    (rpi_adjusted, 'RPI-adjusted', color_rpi, (-12, 35)),
    (cpih_adjusted, 'CPIH-adjusted', color_cpih, (-260, -20)),
):
    ax2.annotate(
        f'{label} (£{series.iloc[-1]:.2f})',
        xy=(series.index[-1].year, series.iloc[-1]),
        xytext=text_offset,
        textcoords='offset points', ha='right', color=color,
        arrowprops=dict(arrowstyle='->', color=color),
    )

all_lines = line1 + line2 + line3 + line4 + line5 + line6
all_labels = [line.get_label() for line in all_lines]
ax1.legend(
    all_lines, all_labels, loc='upper left', frameon=True,
    facecolor='white', edgecolor='#e2e2e2',
)

plt.title(
    'Hampstead Heath Bathing Ponds\nAnnual User Fee Trajectory with RPI and CPIH',
    fontweight='bold', fontsize=14, pad=15,
)
fig.tight_layout()

plt.savefig(repo_root / 'bathing_ponds_fee_trajectory.png', dpi=300)
plt.show()

# %%
