"""Charts of Hampstead Heath finances from City of London committee papers.

--chart sankey (default): Sankey diagram of the Hampstead Heath operating budget.
--chart income: evolving Lido/Ponds income budgets, projections and actuals per
fiscal year, from finance/swimming-income.csv, flagging contradictory restatements.

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
DEFAULT_INCOME_OUTPUT = REPO_ROOT / 'charts' / 'swimming-income-forecasts.png'
DEFAULT_FIGSIZES = {'sankey': (18.0, 10.0), 'income': (14.0, 13.0)}
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


def parse_figsize(value: str) -> tuple[float, float]:
    try:
        width, height = (float(part) for part in value.split(','))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'Invalid --figsize {value!r}; expected "WIDTH,HEIGHT"') from exc
    return width, height


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--chart', choices=('sankey', 'income'), default='sankey',
                        help='sankey: 2025/26 budget Sankey (default); income: Lido/Ponds income forecasts vs actuals')
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
                        help='Figure size in inches (default: 18,10 sankey; 14,13 income)')
    parser.add_argument('--output', type=Path, help='Output PNG (default depends on --chart)')
    parser.add_argument('--show', action='store_true', help='Open an interactive window')
    args = parser.parse_args()
    figsize = args.figsize or DEFAULT_FIGSIZES[args.chart]

    if args.chart == 'income':
        output = args.output or DEFAULT_INCOME_OUTPUT
        fig = draw_income_forecasts(with_combined(load_income(args.data)), args.facilities, args.ytd, figsize)
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
    fig.savefig(output, dpi=150, bbox_inches='tight' if args.chart == 'income' else None)
    print(f'Saved chart to {output}')
    if args.show:
        plt.show()


if __name__ == '__main__':
    main()
