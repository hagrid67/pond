"""Charts of Hampstead Heath finances from City of London committee papers.

--chart sankey (default): Sankey diagram of the Hampstead Heath operating budget.
--chart income: evolving Lido/Ponds income budgets, projections and actuals per
fiscal year, from finance/swimming-income.csv, flagging contradictory restatements.
--chart costs: Lido/Ponds staff, running and one-off costs against income (subsidy shaded).
--chart per-swim: cost and income per swim where swim counts were published.
--chart capital: budget timeline of the swimming facilities safety/access capital project.
--chart maintenance: planned cyclical works for swimming buildings, 2021/22 bids vs 2026/27 list.

Sankey data: 2025/26 projected outturn from the Hampstead Heath Operating Budget table
(Finance Progress Report Q3, Appendix 1), page 147 of the HHHWQP Committee
reports pack for 3 Feb 2026 (col-pdfs/hhhwqp/2026-0203/reports-pack.pdf).

Income sources flow in from the left, through the Heath in the centre, and out
to expenditure categories on the right, broken down by subtotal level.
"""

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.ticker import FuncFormatter

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / 'charts' / 'hh-budget-sankey-2025-26.png'
DEFAULT_INCOME_DATA = REPO_ROOT / 'finance' / 'swimming-income.csv'
FINANCE_DIR = REPO_ROOT / 'finance'
CHART_OUTPUTS = {
    'income': 'swimming-income-forecasts.png',
    'costs': 'swimming-costs.png',
    'per-swim': 'swimming-per-swim.png',
    'capital': 'swimming-capital.png',
    'maintenance': 'swimming-maintenance.png',
}
DEFAULT_FIGSIZES = {
    'sankey': (18.0, 10.0), 'income': (14.0, 13.0), 'costs': (14.0, 10.0), 'per-swim': (12.0, 9.0),
    'capital': (14.0, 10.0), 'maintenance': (12.0, 6.5),
}
SOURCE_NOTE = (
    'Source: City of London, Hampstead Heath, Highgate Wood & Queen\'s Park Committee, 3 Feb 2026 — '
    'Hampstead Heath Operating Budget 2025/26 (reports pack p147), projected outturn.'
)


@dataclass
class Node:
    label: str
    amount: int | None = None
    children: list['Node'] = field(default_factory=list)
    # Subtotal printed in the published table, used to check the encoded hierarchy.
    published: int | None = None
    color: str | None = None
    passthrough: bool = False

    @property
    def value(self) -> int:
        if self.children:
            return sum(child.value for child in self.children)
        return self.amount or 0


def leaf(label: str, amount: int) -> Node:
    return Node(label, amount=amount)


def group(label: str, children: list[Node], published: int | None = None, color: str | None = None) -> Node:
    return Node(label, children=children, published=published, color=color)


def income_tree() -> Node:
    """Income by source; amounts are positive £ (the table shows income in brackets)."""
    operating = group('Operating income\n(Local Risk)', [
        group('Swimming', [leaf('Lido', 1_260_000), leaf('Ponds', 1_140_000)]),
        leaf('Parking', 963_000),
        group('Other operating income', [
            leaf('Facilities', 287_000),
            leaf('Rents, wayleaves & tolls', 210_000),
            leaf('Licences/certificates', 187_000),
            leaf('Film', 137_000),
            leaf('Other', 50_000),
            leaf('Grants & donations', 5_000),
            leaf('Sales', 1_000),
        ]),
    ], published=4_240_000, color='#1f77b4')
    central = group('Investment income\n(Central Risk)', [leaf('Investment income', 1_459_000)],
                    published=1_459_000, color='#2ca02c')
    recharges = group('Recharge income', [leaf('Corporate & Democratic Core', 160_000)],
                      published=160_000, color='#9467bd')
    # The table's Total Net Expenditure is the shortfall funded by the City of London.
    city = group('City of London funding\n(net expenditure)', [leaf('City of London funding', 7_058_000)],
                 published=7_058_000, color='#7f7f7f')
    return group('Income', [operating, central, recharges, city], published=12_917_000)


def expenditure_tree() -> Node:
    local = group('Operating costs\n(Local Risk)', [
        group('Employees', [leaf('Direct employees', 5_750_000), leaf('Indirect employees', 40_000)]),
        group('Premises', [
            leaf('Energy', 275_000), leaf('Water', 150_000), leaf('Cleaning & domestic', 87_000),
            leaf('Rates/council tax', 46_000), leaf('Repairs & maintenance', 5_000),
            leaf('Grounds maintenance', 5_000),
        ], published=568_000),
        group('Transport', [leaf('Direct transport', 70_000), leaf('Other transport', 10_000)],
              published=80_000),
        group('Supplies & services', [
            leaf('Equipment, furniture & materials', 500_000), leaf('Fees & services', 278_000),
            leaf('Other supplies', 105_000),
        ], published=883_000),
    ], published=7_321_000, color='#d62728')
    central = group('Capital charges\n(Central Risk)', [leaf('Capital charges', 408_000)],
                    published=408_000, color='#8c564b')
    recharges = group('Recharges', [
        group('Support services', [
            leaf('Support services', 468_000), leaf('IT recharge', 287_000),
            leaf("Surveyors' employee recharge", 273_000), leaf('Insurance', 97_000),
        ], published=1_125_000),
        leaf('Natural Environment Directorate', 654_000),
        leaf('Structural maintenance (Open Spaces)', 30_000),
    ], published=1_809_000, color='#ff7f0e')
    surveyor = group("City Surveyor's works", [
        leaf('Cyclical Works Programme', 2_952_000),
        group('Facilities management', [leaf('Repairs & maintenance', 412_000),
                                         leaf('Cleaning & pest control', 15_000)], published=427_000),
    ], published=3_379_000, color='#e377c2')
    return group('Expenditure', [local, central, recharges, surveyor], published=12_917_000)


def validate(node: Node, path: str = '') -> list[str]:
    errors = []
    where = f'{path}/{node.label}'.replace('\n', ' ')
    if node.published is not None and node.value != node.published:
        errors.append(f'{where}: sum {node.value:,} != published {node.published:,}')
    for child in node.children:
        errors.extend(validate(child, where))
    return errors


def simplify(node: Node, depth: int, total: int, min_share: float, inherited_color: str | None = None) -> Node:
    """Return a display tree: truncate to depth, merge small siblings, pad short branches."""
    color = node.color or inherited_color
    out = Node(node.label, amount=node.value, color=color, passthrough=node.passthrough)
    children = node.children
    if depth > 0 and children:
        small = [child for child in children if child.value < min_share * total]
        if len(small) >= 2:
            other = Node(f'Other {node.label.split(chr(10))[0].lower()}', amount=sum(c.value for c in small))
            children = [child for child in children if child not in small] + [other]
        largest = max(child.value for child in children)
        if len(children) > 1 and largest < 0.9 * node.value:
            out.children = [simplify(child, depth - 1, total, min_share, color) for child in children]
    if depth > 0 and not out.children:
        # Pad leaves to the outermost column so bands never skip a column; only the outer copy is labelled.
        out.passthrough = True
        out.children = [simplify(Node(node.label, amount=node.value), depth - 1, total, min_share, color)]
    return out


def format_gbp(value: int) -> str:
    return f'£{value / 1e6:.2f}m' if value >= 1_000_000 else f'£{value / 1e3:,.0f}k'


@dataclass
class Placed:
    node: Node
    column: int
    top: float
    height: float


def columns_of(root: Node, sign: int) -> dict[int, list[Node]]:
    columns: dict[int, list[Node]] = {}

    def visit(node: Node, level: int) -> None:
        for child in node.children:
            columns.setdefault(sign * level, []).append(child)
            visit(child, level + 1)

    visit(root, 1)
    return columns


def band(ax, waypoints: list[tuple[float, float]], height: float, color: str) -> None:
    """Fill a band of constant height through (x, top) waypoints joined by S-curves."""
    vertices = [waypoints[0]]
    codes = [MplPath.MOVETO]
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        mid = (x0 + x1) / 2
        vertices += [(mid, y0), (mid, y1), (x1, y1)]
        codes += [MplPath.CURVE4] * 3
    bottom = [(x, y - height) for x, y in reversed(waypoints)]
    vertices.append(bottom[0])
    codes.append(MplPath.LINETO)
    for (x0, y0), (x1, y1) in zip(bottom, bottom[1:]):
        mid = (x0 + x1) / 2
        vertices += [(mid, y0), (mid, y1), (x1, y1)]
        codes += [MplPath.CURVE4] * 3
    vertices.append(waypoints[0])
    codes.append(MplPath.CLOSEPOLY)
    ax.add_patch(PathPatch(MplPath(vertices, codes), facecolor=color, edgecolor='none', alpha=0.35))


def draw_sankey(income: Node, expenditure: Node, figsize: tuple[float, float], title: str) -> plt.Figure:
    total = income.value
    columns = {0: [Node('Hampstead Heath', amount=total, color='#444444')]}
    columns.update(columns_of(income, -1))
    columns.update(columns_of(expenditure, 1))
    gap = 0.018
    max_nodes = max(len(nodes) for nodes in columns.values())
    scale = (1.0 - gap * (max_nodes - 1)) / total
    placed: dict[int, Placed] = {}
    for column, nodes in columns.items():
        height = sum(node.value for node in nodes) * scale + gap * (len(nodes) - 1)
        y = 0.5 + height / 2
        for node in nodes:
            placed[id(node)] = Placed(node, column, y, node.value * scale)
            y -= node.value * scale + gap

    fig, ax = plt.subplots(figsize=figsize)
    width = 0.06
    centre = placed[id(columns[0][0])]

    def link(parent: Placed, children: list[Node], outward: int) -> None:
        offset = parent.top
        for child in children:
            child_place = placed[id(child)]
            # Follow pass-through copies so the band is drawn as one continuous shape.
            chain = [child_place]
            while chain[-1].node.passthrough:
                chain.append(placed[id(chain[-1].node.children[0])])
            waypoints = [(parent.column + outward * width / 2, offset)]
            for place in chain[:-1]:
                waypoints.append((place.column, place.top))
            waypoints.append((chain[-1].column - outward * width / 2, chain[-1].top))
            if outward < 0:
                waypoints.reverse()
            band(ax, waypoints, child_place.height, child.color or '#999999')
            offset -= child_place.height
            link(chain[-1], chain[-1].node.children, outward)

    link(centre, income.children, -1)
    link(centre, expenditure.children, 1)

    outer_left, outer_right = min(columns), max(columns)
    for place in placed.values():
        node = place.node
        color = node.color or '#444444'
        if node.passthrough:
            continue
        ax.add_patch(Rectangle((place.column - width / 2, place.top - place.height), width, place.height,
                               facecolor=color, alpha=0.95, edgecolor='none'))
        is_outer = not node.children
        text = f'{node.label}\n{format_gbp(node.value)}'
        y = place.top - place.height / 2
        if is_outer and place.column in (outer_left, outer_right):
            left = place.column == outer_left
            ax.text(place.column + (-1 if left else 1) * (width / 2 + 0.04), y,
                    f'{node.label.replace(chr(10), " ")}  {format_gbp(node.value)}',
                    ha='right' if left else 'left', va='center', fontsize=9)
        else:
            ax.text(place.column, y, text, ha='center', va='center', fontsize=8.5,
                    fontweight='bold' if place.column == 0 else 'normal',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor=color, alpha=0.9))

    ax.set_xlim(outer_left - 1.1, outer_right + 1.1)
    ax.set_ylim(-0.02, 1.02)
    ax.axis('off')
    ax.text(outer_left - 0.5, 1.03, 'Income', ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.text(outer_right + 0.5, 1.03, 'Expenditure', ha='center', va='bottom', fontsize=12, fontweight='bold')
    fig.suptitle(title, fontsize=14, fontweight='bold')
    fig.text(0.5, 0.015, SOURCE_NOTE, ha='center', fontsize=8.5, style='italic', color='#444444')
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return fig


# --- Swimming income forecasts vs outcomes ---------------------------------------------------

FACILITIES = ('lido', 'ponds', 'combined')
FACILITY_TITLES = {'lido': 'Parliament Hill Lido', 'ponds': 'Bathing Ponds', 'combined': 'Lido + Ponds combined'}
FINAL_FIGURES = ('annual_review_actual', 'actual', 'outturn_derived')
# Plot order within a report: budget first, then year-to-date, projection, and final figures.
FIGURE_ORDER = {'latest_budget': 0, 'actual_to_date': 1, 'projected_outturn': 2,
                'annual_review_actual': 3, 'actual': 4, 'outturn_derived': 5}
FIGURE_STYLES = {
    'latest_budget': dict(marker='s', s=60, label='Budget (hollow)'),
    'actual_to_date': dict(marker='^', s=38, label='Actual to date (part year)'),
    'projected_outturn': dict(marker='o', s=55, label='Projected outturn'),
    'annual_review_actual': dict(marker='D', s=95, label='Actual: annual swimming review'),
    'actual': dict(marker='D', s=95, label='Actual: later revenue report'),
    'outturn_derived': dict(marker='P', s=120, label='Outturn derived from budget + variance'),
}
CONTRADICTION_TOLERANCE = 0.05
INCOME_SOURCE_NOTE = (
    'Source: Hampstead Heath, Highgate Wood & Queen\'s Park Committee papers 2020–2026 (finance/swimming-income.csv). '
    'Points within a year are ordered by report date; colour = report date.'
)


@dataclass(frozen=True)
class Estimate:
    fiscal_year: str
    facility: str
    figure: str
    value: int
    report_date: date

    @property
    def is_final(self) -> bool:
        return self.figure in FINAL_FIGURES


def load_income(path: Path) -> list[Estimate]:
    with path.open(newline='', encoding='utf-8') as handle:
        return [
            Estimate(row['fiscal_year'], 'combined' if row['facility'] == 'ponds+lido' else row['facility'],
                     row['figure'], int(row['value_gbp']), date.fromisoformat(row['report_date']))
            for row in csv.DictReader(handle) if row['figure'] in FIGURE_ORDER
        ]


def with_combined(estimates: list[Estimate]) -> list[Estimate]:
    """Add combined figures summing Lido and Ponds from the same report, unless stated directly."""
    stated = {(e.fiscal_year, e.figure, e.report_date) for e in estimates if e.facility == 'combined'}
    parts: dict[tuple, dict[str, int]] = defaultdict(dict)
    for e in estimates:
        if e.facility in ('lido', 'ponds'):
            parts[(e.fiscal_year, e.figure, e.report_date)][e.facility] = e.value
    combined = [
        Estimate(year, 'combined', figure, values['lido'] + values['ponds'], report_date)
        for (year, figure, report_date), values in parts.items()
        if len(values) == 2 and (year, figure, report_date) not in stated
    ]
    return estimates + combined


def drop_repeats(estimates: list[Estimate]) -> list[Estimate]:
    """Keep only the first report of an identical restated figure."""
    seen = set()
    kept = []
    for e in sorted(estimates, key=lambda item: item.report_date):
        key = (e.fiscal_year, e.facility, e.figure, e.value)
        if key not in seen:
            seen.add(key)
            kept.append(e)
    return kept


def find_contradictions(estimates: list[Estimate]) -> dict[Estimate, str]:
    """Flag final figures that disagree with an earlier final figure, or fall below a year-to-date actual."""
    groups: dict[tuple[str, str], list[Estimate]] = defaultdict(list)
    for e in estimates:
        groups[(e.facility, e.fiscal_year)].append(e)
    flags = {}
    for items in groups.values():
        items.sort(key=lambda item: (item.report_date, FIGURE_ORDER[item.figure]))
        finals = [e for e in items if e.is_final]
        for index, final in enumerate(finals):
            reasons = []
            for earlier in finals[:index]:
                if abs(final.value - earlier.value) > CONTRADICTION_TOLERANCE * earlier.value:
                    reasons.append(f'≠ {format_k(earlier.value)} ({earlier.report_date:%b %Y})')
            year_to_date = [e for e in items if e.figure == 'actual_to_date' and e.report_date <= final.report_date]
            highest = max(year_to_date, key=lambda item: item.value, default=None)
            if highest is not None and final.value < (1 - CONTRADICTION_TOLERANCE) * highest.value:
                reasons.append(f'< YTD {format_k(highest.value)} ({highest.report_date:%b %Y})')
            if reasons:
                flags[final] = '; '.join(reasons)
    return flags


def format_k(value: float) -> str:
    return f'£{value / 1000:,.0f}k'


def fiscal_start(fiscal_year: str) -> int:
    return int(fiscal_year[:4])


def draw_income_forecasts(
    estimates: list[Estimate], facilities: list[str], show_ytd: bool, figsize: tuple[float, float],
) -> plt.Figure:
    unique = drop_repeats(estimates)
    flags = find_contradictions(unique)
    shown = [e for e in unique if show_ytd or e.figure != 'actual_to_date']
    first_year = min(fiscal_start(e.fiscal_year) for e in shown)
    years = list(range(first_year, max(fiscal_start(e.fiscal_year) for e in shown) + 1))
    dates = [mdates.date2num(e.report_date) for e in shown]
    norm = plt.Normalize(min(dates), max(dates))
    cmap = plt.get_cmap('viridis')
    fig, axes = plt.subplots(len(facilities), 1, figsize=figsize, sharex=True, squeeze=False,
                             layout='constrained')
    for ax, facility in zip(axes[:, 0], facilities):
        groups: dict[str, list[Estimate]] = defaultdict(list)
        for e in shown:
            if e.facility == facility:
                groups[e.fiscal_year].append(e)
        for fiscal_year, items in groups.items():
            items.sort(key=lambda item: (item.report_date, FIGURE_ORDER[item.figure]))
            offsets = np.linspace(-0.32, 0.32, len(items)) if len(items) > 1 else [0.0]
            xs = [fiscal_start(fiscal_year) + offset for offset in offsets]
            trail = [(x, e.value / 1000) for x, e in zip(xs, items) if e.figure != 'actual_to_date']
            if len(trail) > 1:
                ax.plot(*zip(*trail), color='#999999', linewidth=1, zorder=1)
            # Label the last projection when the year has no final figure yet.
            unfinished = not any(e.is_final for e in items)
            last_projection = next((e for e in reversed(items) if e.figure == 'projected_outturn'), None)
            labelled = 0
            for x, e in zip(xs, items):
                style = dict(FIGURE_STYLES[e.figure])
                style.pop('label')
                color = cmap(norm(mdates.date2num(e.report_date)))
                hollow = e.figure == 'latest_budget'
                ax.scatter(x, e.value / 1000, facecolors='none' if hollow else [color],
                           edgecolors=[color] if hollow else 'black', linewidths=1.6 if hollow else 0.6,
                           zorder=3, **style)
                if e.is_final or (unfinished and e is last_projection):
                    # Alternate above/below so adjacent actuals in the same year stay legible.
                    below = labelled % 2 == 1 and e not in flags
                    ax.annotate(format_k(e.value), (x, e.value / 1000), xytext=(0, -11 if below else 9),
                                textcoords='offset points', ha='center', va='top' if below else 'baseline',
                                fontsize=8, fontweight='bold')
                    labelled += 1
                if e in flags:
                    ax.scatter(x, e.value / 1000, marker='x', s=190, color='#d62728', linewidths=2.2, zorder=4)
                    ax.annotate(flags[e], (x, e.value / 1000), xytext=(8, -14), textcoords='offset points',
                                fontsize=7.5, color='#d62728', ha='left',
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85))
        for year in years:
            if f'{year}/{(year + 1) % 100:02d}' not in groups:
                ax.text(year, 0.04, 'no figures\nfound', transform=ax.get_xaxis_transform(), ha='center',
                        va='bottom', fontsize=8, color='#888888', style='italic')
        ax.set_title(FACILITY_TITLES[facility], fontweight='bold', loc='left')
        ax.set_ylabel('Income (£k)')
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'£{value:,.0f}k'))
        ax.grid(True, axis='y', linestyle=':', alpha=0.6)
        for year in years[:-1]:
            ax.axvline(year + 0.5, color='#e2e2e2', linewidth=0.8, zorder=0)
    last = axes[-1, 0]
    last.set_xticks(years)
    last.set_xticklabels([f'{year}/{(year + 1) % 100:02d}' for year in years])
    last.set_xlim(years[0] - 0.5, years[-1] + 0.5)
    last.set_xlabel('Fiscal year (April–March)')
    handles = [Line2D([], [], linestyle='none', markerfacecolor='none' if key == 'latest_budget' else '#888888',
                      markeredgecolor='#555555', marker=style['marker'], markersize=8, label=style['label'])
               for key, style in FIGURE_STYLES.items() if show_ytd or key != 'actual_to_date']
    handles.append(Line2D([], [], linestyle='none', marker='x', color='#d62728', markersize=10, markeredgewidth=2,
                          label='Contradicts earlier figure'))
    legend = fig.legend(handles=handles, loc='outside lower center', fontsize=8.5, frameon=False, ncol=4,
                        title=INCOME_SOURCE_NOTE, title_fontsize=8)
    legend.get_title().set(style='italic', color='#444444')
    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axes[:, 0], pad=0.01, aspect=40)
    colorbar.set_label('Report date')
    colorbar.ax.yaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.suptitle('Hampstead Heath swimming income: budgets, forecasts and actuals by report',
                 fontsize=14, fontweight='bold')
    return fig


# --- Shared helpers for the finance CSVs ------------------------------------------------------

COLOR_STAFF, COLOR_RUNNING, COLOR_ONE_OFF = '#4c72b0', '#dd8452', '#8172b3'
COLOR_SUBSIDY, COLOR_CONTRADICTION = '#c44e52', '#d62728'
FINANCE_NOTE = 'Source: Hampstead Heath, Highgate Wood & Queen\'s Park Committee papers (finance/*.csv, with page references).'


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def year_label(year: int) -> str:
    return f'{year}/{(year + 1) % 100:02d}'


def money_axis(ax, unit: str = 'k') -> None:
    if unit == 'k':
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'£{value:,.0f}k'))
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'£{value:,.2f}'))
    ax.grid(True, axis='y', linestyle=':', alpha=0.6)


def income_by_year(income_rows: list[dict[str, str]], facility: str) -> dict[str, dict[str, int]]:
    """Per fiscal year: annual review income, first-reported ledger actual, and latest projection."""
    result: dict[str, dict[str, int]] = defaultdict(dict)
    for row in sorted(income_rows, key=lambda item: item['report_date']):
        if row['facility'] != facility:
            continue
        value, year = int(row['value_gbp']), row['fiscal_year']
        if row['figure'] == 'annual_review_actual':
            result[year]['review'] = value
        elif row['figure'] == 'actual':
            result[year].setdefault('ledger', value)
        elif row['figure'] in ('projected_outturn', 'outturn_derived'):
            result[year]['projection'] = value
    return result


# --- Costs vs income (--chart costs) ----------------------------------------------------------

COST_COMPONENTS = (('employee', 'Staff', COLOR_STAFF), ('operational', 'Running costs', COLOR_RUNNING),
                   ('one_off', 'One-off: access project', COLOR_ONE_OFF))


def costs_by_year(cost_rows: list[dict[str, str]], facility: str) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(dict)
    for row in cost_rows:
        if row['facility'] == facility:
            result[row['fiscal_year']][row['category']] = int(row['value_gbp'])
    return result


def draw_costs(cost_rows, income_rows, figsize) -> plt.Figure:
    facilities = (('ponds', 'Bathing Ponds'), ('lido', 'Parliament Hill Lido'))
    years = list(range(2018, 2026))
    fig, axes = plt.subplots(len(facilities), 1, figsize=figsize, sharex=True, layout='constrained')
    for ax, (facility, title) in zip(axes, facilities):
        costs, income = costs_by_year(cost_rows, facility), income_by_year(income_rows, facility)
        top = 0
        for year in years:
            label = year_label(year)
            parts, incomes = costs.get(label, {}), income.get(label, {})
            bottom = 0
            for key, name, color in COST_COMPONENTS:
                if key in parts:
                    ax.bar(year, parts[key] / 1000, 0.6, bottom=bottom, color=color, label=name)
                    bottom += parts[key] / 1000
            if not bottom and 'total_expenditure' in parts:
                bottom = parts['total_expenditure'] / 1000
                ax.bar(year, bottom, 0.6, color='#bbbbbb', label='Total cost (no breakdown)')
            if bottom:
                ax.annotate(f'£{bottom:,.0f}k', (year, bottom), xytext=(0, 3), textcoords='offset points',
                            ha='center', fontsize=8, fontweight='bold')
            elif year >= 2023:
                ax.text(year, 0.04, 'cost breakdown\nno longer\npublished', transform=ax.get_xaxis_transform(),
                        ha='center', va='bottom', fontsize=8, color='#888888', style='italic')
            else:
                ax.text(year, 0.04, 'no figures\nfound', transform=ax.get_xaxis_transform(),
                        ha='center', va='bottom', fontsize=8, color='#888888', style='italic')
            review = incomes.get('review')
            actual = review or incomes.get('ledger')
            if bottom and actual is not None and actual < bottom * 1000:
                subsidy = parts.get('subsidy', bottom * 1000 - actual)
                ax.bar(year, bottom - actual / 1000, 0.6, bottom=actual / 1000, facecolor='none',
                       edgecolor=COLOR_SUBSIDY, hatch='///', linewidth=0, label='Subsidy (cost − income)')
                ax.annotate(f'subsidy £{subsidy / 1000:,.0f}k ({subsidy / (bottom * 1000):.0%})', (year, bottom),
                            xytext=(0, 14), textcoords='offset points', ha='center', fontsize=7.5,
                            color=COLOR_SUBSIDY)
            if review is not None:
                ax.scatter(year, review / 1000, marker='D', s=70, color='black', zorder=4,
                           label='Income: annual swimming review')
            ledger = incomes.get('ledger')
            if ledger is not None and (review is None or abs(ledger - review) > 0.05 * review):
                contradicts = review is not None
                ax.scatter(year, ledger / 1000, marker='D', s=70, zorder=4,
                           facecolor='white', edgecolor=COLOR_CONTRADICTION if contradicts else 'black',
                           linewidths=1.8, label='Income: revenue report actual')
                if contradicts:
                    ax.plot([year, year], [review / 1000, ledger / 1000], color=COLOR_CONTRADICTION,
                            linestyle='--', linewidth=1.2, zorder=3)
                    ax.annotate(f'revenue report:\n£{ledger / 1000:,.0f}k', (year - 0.3, ledger / 1000), xytext=(-4, 0),
                                textcoords='offset points', ha='right', va='center', fontsize=7.5,
                                color=COLOR_CONTRADICTION)
            elif review is None and ledger is None and 'projection' in incomes:
                ax.scatter(year, incomes['projection'] / 1000, marker='o', s=60, facecolor='white',
                           edgecolor='black', linewidths=1.5, zorder=4, label='Income: latest projection')
            top = max(top, bottom, *(value / 1000 for value in incomes.values()))
        ax.set_title(title, fontweight='bold', loc='left')
        ax.set_ylabel('£k per year')
        ax.set_ylim(0, top * 1.18)
        money_axis(ax)
    axes[-1].set_xticks(years, [year_label(year) for year in years])
    axes[-1].set_xlabel('Fiscal year (April–March)')
    handles: dict[str, object] = {}
    for ax in axes:
        for handle, label in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(label, handle)
    legend = fig.legend(handles.values(), handles.keys(), loc='outside lower center', ncol=4, fontsize=8.5,
                        frameon=False, title=FINANCE_NOTE + ' Costs from the annual swimming reviews; '
                        '2020/21 affected by Covid closures.', title_fontsize=8)
    legend.get_title().set(style='italic', color='#444444')
    fig.suptitle('Hampstead Heath swimming: costs against income', fontsize=14, fontweight='bold')
    return fig


# --- Cost and income per swim (--chart per-swim) ----------------------------------------------

def per_swim_figures(cost_rows, income_rows, swim_rows) -> list[dict]:
    """Join swims with total cost and income for each facility-year where swims were published."""
    results = []
    for row in swim_rows:
        year, facility, swims = row['fiscal_year'], row['facility'], int(row['swims'])
        parts = ('lido', 'ponds') if facility == 'ponds+lido' else (facility,)
        cost = one_off = income = 0
        has_cost = has_income = True
        for part in parts:
            costs = costs_by_year(cost_rows, part).get(year, {})
            incomes = income_by_year(income_rows, part).get(year, {})
            has_cost &= 'total_expenditure' in costs
            cost += costs.get('total_expenditure', 0)
            one_off += costs.get('one_off', 0)
            value = incomes.get('review', incomes.get('projection'))
            has_income &= value is not None
            income += value or 0
        results.append({
            'year': year, 'facility': facility, 'swims': swims,
            'cost': cost / swims if has_cost else None, 'one_off': one_off / swims,
            'income': income / swims if has_income else None,
            'caveat': bool(row.get('note')),
        })
    return results


def draw_per_swim(cost_rows, income_rows, swim_rows, figsize) -> plt.Figure:
    figures = per_swim_figures(cost_rows, income_rows, swim_rows)
    panels = [('ponds', 'Bathing Ponds'), ('lido', 'Parliament Hill Lido'), ('ponds+lido', 'Lido + Ponds combined')]
    years = sorted({int(item['year'][:4]) for item in figures})
    fig, axes = plt.subplots(len(panels), 1, figsize=figsize, sharex=True, layout='constrained')
    for ax, (facility, title) in zip(axes, panels):
        for item in (f for f in figures if f['facility'] == facility):
            x = int(item['year'][:4])
            if item['cost'] is not None:
                recurring = item['cost'] - item['one_off']
                ax.bar(x, recurring, 0.6, color=COLOR_STAFF, label='Cost per swim')
                if item['one_off']:
                    ax.bar(x, item['one_off'], 0.6, bottom=recurring, color=COLOR_ONE_OFF,
                           label='One-off access project per swim')
                ax.annotate(f'£{item["cost"]:.2f}', (x, item['cost']), xytext=(0, 3), textcoords='offset points',
                            ha='center', fontsize=8.5, fontweight='bold')
            top = max(value for value in (item['cost'], item['income']) if value is not None)
            ax.annotate(f'{item["swims"]:,} swims{"*" if item["caveat"] else ""}', (x, top), xytext=(0, 16),
                        textcoords='offset points', ha='center', fontsize=7.5, color='#555555')
            if item['income'] is not None:
                ax.scatter(x, item['income'], marker='D', s=70, color='black', zorder=4, label='Income per swim')
                ax.annotate(f'£{item["income"]:.2f}', (x, item['income']), xytext=(9, 0),
                            textcoords='offset points', va='center', fontsize=8.5)
                if item['cost'] is not None and item['income'] < item['cost']:
                    ax.bar(x, item['cost'] - item['income'], 0.6, bottom=item['income'], facecolor='none',
                           edgecolor=COLOR_SUBSIDY, hatch='///', linewidth=0, label='Subsidy per swim')
        ax.set_title(title, fontweight='bold', loc='left')
        ax.set_ylabel('£ per swim')
        money_axis(ax, unit='£')
        ax.set_ylim(0, ax.get_ylim()[1] * 1.25)
    axes[-1].set_xticks(years, [year_label(year) for year in years])
    axes[-1].set_xlim(years[0] - 0.6, years[-1] + 0.6)
    axes[-1].set_xlabel('Fiscal year (April–March); only years with published swim counts')
    handles: dict[str, object] = {}
    for ax in axes:
        for handle, label in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(label, handle)
    legend = fig.legend(handles.values(), handles.keys(), loc='outside lower center', ncol=4, fontsize=8.5,
                        frameon=False, title=FINANCE_NOTE + ' *2018/19 swims estimated; 2020/21 swims Jul–Jan only (Covid); '
                        '2025/26 income is the Feb 2026 projection.', title_fontsize=8)
    legend.get_title().set(style='italic', color='#444444')
    fig.suptitle('Hampstead Heath swimming: cost and income per swim', fontsize=14, fontweight='bold')
    return fig


# --- Capital project timeline (--chart capital) -----------------------------------------------

SWIMMING_PROJECT = 'Swimming Facilities - Safety, Access & Security Improvements'
LIDO_PV_PROJECT = 'Parliament Hill Lido Photovoltaic Panels'
CAPITAL_GAP_DAYS = 450
CAPITAL_MILESTONES = (
    ('2022-02-09', 'Gateway 2:\n£697k (£755k incl. risk)'),
    ('2022-06-15', 'Gateway 3/4:\n£691k'),
    ('2023-02-08', 'All tenders above\n£490k estimate'),
    ('2023-07-17', '£257k from Heath\nlocal risk budget'),
    ('2025-10-21', 'First reported at\n£1,011k'),
)


def capital_series(rows, project: str, measures: tuple[str, ...]) -> list[tuple[date, int]]:
    by_date: dict[date, int] = {}
    for row in rows:
        if row['project'] == project and row['measure'] in measures:
            by_date[date.fromisoformat(row['report_date'])] = int(row['value_gbp'])
    return sorted(by_date.items())


def step_with_gaps(ax, series, color: str, label: str, end: date) -> None:
    """Step line; segments spanning more than a year with no reports are dashed."""
    points = series + [(end, series[-1][1])]
    for (d0, v0), (d1, v1) in zip(points, points[1:]):
        gap = (d1 - d0).days > CAPITAL_GAP_DAYS
        ax.plot([d0, d1], [v0 / 1000, v0 / 1000], color=color, linewidth=2.2,
                linestyle='--' if gap else '-', label=label)
        ax.plot([d1, d1], [v0 / 1000, v1 / 1000], color=color, linewidth=2.2, linestyle='--' if gap else '-')
        label = None
    ax.scatter([d for d, _ in series], [v / 1000 for _, v in series], color=color, s=30, zorder=4)


def draw_capital(rows, figsize) -> plt.Figure:
    estimate = capital_series(rows, SWIMMING_PROJECT,
                              ('total_estimated_cost_excl_risk', 'estimated_cost', 'total_estimated_cost'))
    approved = capital_series(rows, SWIMMING_PROJECT, ('approved_budget',))
    spent = capital_series(rows, SWIMMING_PROJECT, ('spent_to_date', 'spent_and_committed'))
    award = capital_series(rows, SWIMMING_PROJECT, ('capital_funding_awarded',))[0]
    pre_tender = capital_series(rows, SWIMMING_PROJECT, ('pre_tender_estimate',))
    end = date(2027, 1, 31)
    fig, (ax, ax_pv) = plt.subplots(2, 1, figsize=figsize, sharex=True, layout='constrained',
                                    gridspec_kw={'height_ratios': [3, 1]})
    gap_start = max(d for d, _ in estimate if d.year <= 2023)
    gap_end = min(d for d, _ in estimate if d.year >= 2025)
    for axis in (ax, ax_pv):
        axis.axvspan(gap_start, gap_end, color='#f2f2f2', zorder=0)
    ax.text(gap_start + (gap_end - gap_start) / 2, 0.97, 'No budget updates in\nthis committee\'s papers',
            transform=ax.get_xaxis_transform(), ha='center', va='top', fontsize=8.5, color='#777777', style='italic')
    ax.axhline(award[1] / 1000, color='#555555', linestyle=':', linewidth=1.4)
    ax.scatter(award[0], award[1] / 1000, marker='*', s=160, color='#555555', zorder=5)
    ax.annotate(f'£{award[1] / 1000:,.0f}k awarded {award[0]:%b %Y}', (award[0], award[1] / 1000), xytext=(8, 4),
                textcoords='offset points', fontsize=8, color='#555555')
    spent_label = 'Spent to date (incl. committed at gateways)'
    for (d0, v0), (d1, v1) in zip(spent, spent[1:]):
        # Spending between reports more than CAPITAL_GAP_DAYS apart is unknown: shade it faintly.
        gap = (d1 - d0).days > CAPITAL_GAP_DAYS
        ax.fill_between([d0, d1], [v0 / 1000, v1 / 1000], color='#55a868', alpha=0.12 if gap else 0.35,
                        linewidth=0, label=None if gap else spent_label)
        if not gap:
            spent_label = None
        ax.plot([d0, d1], [v0 / 1000, v1 / 1000], color='#55a868', linestyle=':' if gap else '-')
    ax.scatter([d for d, _ in spent], [v / 1000 for _, v in spent], color='#55a868', s=18, zorder=4)
    step_with_gaps(ax, estimate, '#c44e52', 'Total estimated cost', end)
    step_with_gaps(ax, approved, '#4c72b0', 'Approved budget', end)
    for d, value in pre_tender:
        ax.scatter(d, value / 1000, marker='x', s=80, color='black', zorder=5, label='Pre-tender estimate')
    for index, (when, text) in enumerate(CAPITAL_MILESTONES):
        when = date.fromisoformat(when)
        ax.axvline(when, color='#999999', linewidth=0.8, linestyle='-', zorder=1)
        ax.text(when, 1210 - 110 * (index % 2), text, fontsize=7.5, ha='left', va='top', color='#333333',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#cccccc', alpha=0.9))
    final = estimate[-1][1]
    ax.annotate(f'£{final / 1000:,.0f}k\n+{final / award[1] - 1:.0%} vs £{award[1] / 1000:,.0f}k',
                (end, final / 1000), xytext=(6, 0), textcoords='offset points', va='center', fontsize=9,
                fontweight='bold', color='#c44e52')
    ax.set_ylim(0, 1250)
    ax.set_ylabel('£k')
    money_axis(ax)
    ax.set_title('Swimming Facilities – Safety, Access & Security Improvements', fontweight='bold', loc='left')
    ax.legend(loc='upper center', bbox_to_anchor=(0.66, 0.83), fontsize=8.5)
    pv_cost = capital_series(rows, LIDO_PV_PROJECT, ('total_estimated_cost',))
    pv_spent = capital_series(rows, LIDO_PV_PROJECT, ('spent_to_date',))
    ax_pv.plot(*zip(*[(d, v / 1000) for d, v in pv_cost]), color='#c44e52', marker='o', label='Total estimated cost')
    ax_pv.plot(*zip(*[(d, v / 1000) for d, v in pv_spent]), color='#55a868', marker='o', label='Spent to date')
    for d, value in pv_cost:
        ax_pv.annotate(f'£{value / 1000:,.0f}k', (d, value / 1000), xytext=(6, 2), textcoords='offset points',
                       fontsize=8)
    ax_pv.set_ylim(0, 550)
    ax_pv.set_ylabel('£k')
    money_axis(ax_pv)
    ax_pv.set_title('Parliament Hill Lido photovoltaic panels', fontweight='bold', loc='left')
    ax_pv.legend(loc='upper left', fontsize=8)
    ax_pv.set_xlim(date(2021, 3, 1), end)
    ax_pv.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax_pv.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax_pv.set_xlabel('Report date. Sources: finance/swimming-capital.csv; 2025–26 figures from OCR of image tables.',
                     fontsize=8.5)
    fig.suptitle('Hampstead Heath swimming capital projects: budget and spend by report date',
                 fontsize=14, fontweight='bold')
    return fig


# --- Planned maintenance (--chart maintenance) ------------------------------------------------

MAINTENANCE_BUILDINGS = (
    ('Parliament Hill Lido', ('Lido',)),
    ("Men's Pond", ('Mens', "Men's", 'Highgate Ponds')),
    ("Ladies' Pond", ('Ladies', 'Kenwood')),
    ('Mixed Pond', ('Mixed',)),
)


def maintenance_building(item: str) -> str:
    for building, keys in MAINTENANCE_BUILDINGS:
        if any(key in item for key in keys):
            return building
    return 'All ponds: infrastructure'


def draw_maintenance(rows, figsize) -> plt.Figure:
    planned = [row for row in rows if row['kind'] == 'planned_cwp']
    years = sorted({row['fiscal_year'] for row in planned})
    buildings = [name for name, _ in MAINTENANCE_BUILDINGS] + ['All ponds: infrastructure']
    totals = {(b, y): 0 for b in buildings for y in years}
    counts = dict.fromkeys(totals, 0)
    for row in planned:
        key = (maintenance_building(row['item']), row['fiscal_year'])
        totals[key] += int(row['value_gbp'])
        counts[key] += 1
    fig, ax = plt.subplots(figsize=figsize, layout='constrained')
    colors = ('#8c8c8c', '#4c72b0')
    height = 0.38
    for index, year in enumerate(years):
        ys = [len(buildings) - 1 - b + (0.5 - index) * height for b in range(len(buildings))]
        values = [totals[(building, year)] / 1000 for building in buildings]
        ax.barh(ys, values, height, color=colors[index % 2],
                label=f'{year} CWP ({"bids" if index == 0 else "project list"}): '
                      f'£{sum(values):,.0f}k total')
        for y, value, building in zip(ys, values, buildings):
            n = counts[(building, year)]
            ax.annotate(f'£{value:,.1f}k ({n} item{"s" if n != 1 else ""})' if n else 'none',
                        (value, y), xytext=(4, 0), textcoords='offset points', va='center', fontsize=8.5)
    ax.set_yticks(range(len(buildings) - 1, -1, -1), buildings)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f'£{value:,.0f}k'))
    ax.grid(True, axis='x', linestyle=':', alpha=0.6)
    ax.set_xlim(0, max(totals.values()) / 1000 * 1.3)
    ax.legend(loc='lower right', fontsize=9)
    ax.set_xlabel('Planned Cyclical Works Programme spend (£k). Largest 2026/27 item: '
                  'Lido landlord\'s lighting & power rewire £180k (£30k in the 2021/22 bids). '
                  'Source: finance/swimming-maintenance.csv.', fontsize=8.5)
    fig.suptitle('Planned repairs and maintenance for swimming buildings', fontsize=14, fontweight='bold')
    return fig


def parse_figsize(value: str) -> tuple[float, float]:
    try:
        width, height = (float(part) for part in value.split(','))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'Invalid --figsize {value!r}; expected "WIDTH,HEIGHT"') from exc
    return width, height


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--chart', choices=('sankey', *CHART_OUTPUTS), default='sankey',
                        help='sankey (default), income, costs, per-swim, capital or maintenance; see description')
    parser.add_argument('--depth', type=int, default=3,
                        help='Sankey: levels of breakdown on each side of the centre (default: 3)')
    parser.add_argument('--min-share', type=float, default=0.025,
                        help='Sankey: merge sibling items below this share of the total into "Other" (default: 0.025)')
    parser.add_argument('--data', type=Path, default=DEFAULT_INCOME_DATA,
                        help='Income: CSV of income figures (default: finance/swimming-income.csv)')
    parser.add_argument('--facilities', nargs='+', choices=FACILITIES, default=list(FACILITIES),
                        help='Income: panels to draw (default: lido ponds combined)')
    parser.add_argument('--no-ytd', dest='ytd', action='store_false',
                        help='Income: hide part-year actual-to-date points (still used to flag contradictions)')
    parser.add_argument('--figsize', type=parse_figsize, metavar='WIDTH,HEIGHT',
                        help='Figure size in inches (default depends on --chart)')
    parser.add_argument('--output', type=Path, help='Output PNG (default depends on --chart)')
    parser.add_argument('--show', action='store_true', help='Open an interactive window')
    args = parser.parse_args()
    figsize = args.figsize or DEFAULT_FIGSIZES[args.chart]

    if args.chart != 'sankey':
        output = args.output or REPO_ROOT / 'charts' / CHART_OUTPUTS[args.chart]
    if args.chart == 'income':
        fig = draw_income_forecasts(with_combined(load_income(args.data)), args.facilities, args.ytd, figsize)
    elif args.chart == 'costs':
        fig = draw_costs(read_rows(FINANCE_DIR / 'swimming-costs.csv'), read_rows(args.data), figsize)
    elif args.chart == 'per-swim':
        fig = draw_per_swim(read_rows(FINANCE_DIR / 'swimming-costs.csv'), read_rows(args.data),
                            read_rows(FINANCE_DIR / 'swim-counts.csv'), figsize)
    elif args.chart == 'capital':
        fig = draw_capital(read_rows(FINANCE_DIR / 'swimming-capital.csv'), figsize)
    elif args.chart == 'maintenance':
        fig = draw_maintenance(read_rows(FINANCE_DIR / 'swimming-maintenance.csv'), figsize)
    else:
        output = args.output or DEFAULT_OUTPUT
        income, expenditure = income_tree(), expenditure_tree()
        errors = validate(income) + validate(expenditure)
        if errors:
            raise SystemExit('Budget hierarchy does not match published subtotals:\n' + '\n'.join(errors))
        total = income.value
        fig = draw_sankey(
            simplify(income, args.depth, total, args.min_share),
            simplify(expenditure, args.depth, total, args.min_share),
            figsize,
            f'Hampstead Heath budget 2025/26 (projected outturn) — {format_gbp(total)}',
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches=None if args.chart == 'sankey' else 'tight')
    print(f'Saved chart to {output}')
    if args.show:
        plt.show()


if __name__ == '__main__':
    main()
