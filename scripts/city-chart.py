"""Draw a Sankey diagram of the Hampstead Heath operating budget.

Data: 2025/26 projected outturn from the Hampstead Heath Operating Budget table
(Finance Progress Report Q3, Appendix 1), page 147 of the HHHWQP Committee
reports pack for 3 Feb 2026 (col-pdfs/hhhwqp/2026-0203/reports-pack.pdf).

Income sources flow in from the left, through the Heath in the centre, and out
to expenditure categories on the right, broken down by subtotal level.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / 'charts' / 'hh-budget-sankey-2025-26.png'
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


def parse_figsize(value: str) -> tuple[float, float]:
    try:
        width, height = (float(part) for part in value.split(','))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'Invalid --figsize {value!r}; expected "WIDTH,HEIGHT"') from exc
    return width, height


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', type=int, default=3,
                        help='Levels of breakdown on each side of the centre (default: 3)')
    parser.add_argument('--min-share', type=float, default=0.025,
                        help='Merge sibling items below this share of the total into "Other" (default: 0.025)')
    parser.add_argument('--figsize', type=parse_figsize, default=(18.0, 10.0), metavar='WIDTH,HEIGHT')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--show', action='store_true', help='Open an interactive window')
    args = parser.parse_args()

    income, expenditure = income_tree(), expenditure_tree()
    errors = validate(income) + validate(expenditure)
    if errors:
        raise SystemExit('Budget hierarchy does not match published subtotals:\n' + '\n'.join(errors))
    total = income.value
    fig = draw_sankey(
        simplify(income, args.depth, total, args.min_share),
        simplify(expenditure, args.depth, total, args.min_share),
        args.figsize,
        f'Hampstead Heath budget 2025/26 (projected outturn) — {format_gbp(total)}',
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f'Saved chart to {args.output}')
    if args.show:
        plt.show()


if __name__ == '__main__':
    main()
