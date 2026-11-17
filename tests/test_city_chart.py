import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'city-chart.py'
spec = importlib.util.spec_from_file_location('city_chart', SCRIPT)
city_chart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(city_chart)


def test_budget_hierarchy_matches_published_subtotals() -> None:
    income, expenditure = city_chart.income_tree(), city_chart.expenditure_tree()
    assert city_chart.validate(income) == []
    assert city_chart.validate(expenditure) == []
    assert income.value == expenditure.value == 12_917_000


def test_simplify_preserves_values_at_every_column() -> None:
    expenditure = city_chart.expenditure_tree()
    display = city_chart.simplify(expenditure, 3, expenditure.value, 0.025)
    for column in city_chart.columns_of(display, 1).values():
        assert sum(node.value for node in column) == expenditure.value


def test_income_contradictions_flag_split_change_and_actual_below_year_to_date() -> None:
    estimates = city_chart.with_combined(city_chart.load_income(city_chart.DEFAULT_INCOME_DATA))
    flags = city_chart.find_contradictions(city_chart.drop_repeats(estimates))
    flagged = {(e.facility, e.fiscal_year, e.value): reason for e, reason in flags.items()}

    assert flagged[('ponds', '2022/23', 176_043)] == '≠ £823k (Jul 2023)'
    assert flagged[('ponds', '2024/25', 214_726)] == '< YTD £786k (Feb 2025)'
    # The combined 2022/23 totals agree within the tolerance, so they are not flagged.
    assert not any(key[:2] == ('combined', '2022/23') for key in flagged)


def test_with_combined_sums_lido_and_ponds_from_the_same_report() -> None:
    estimates = city_chart.with_combined(city_chart.load_income(city_chart.DEFAULT_INCOME_DATA))
    q3_2024 = [e for e in estimates if e.facility == 'combined' and e.fiscal_year == '2024/25'
               and e.figure == 'projected_outturn' and str(e.report_date) == '2025-02-04']
    assert [e.value for e in q3_2024] == [2_045_000]


def test_per_swim_figures_join_costs_income_and_swims() -> None:
    finance = city_chart.FINANCE_DIR
    figures = city_chart.per_swim_figures(
        city_chart.read_rows(finance / 'swimming-costs.csv'), city_chart.read_rows(city_chart.DEFAULT_INCOME_DATA),
        city_chart.read_rows(finance / 'swim-counts.csv'),
    )
    by_key = {(f['facility'], f['year']): f for f in figures}
    ponds = by_key[('ponds', '2022/23')]
    assert (round(ponds['cost'], 2), round(ponds['one_off'], 2), round(ponds['income'], 2)) == (3.09, 0.95, 2.23)
    # Combined 2020/21 sums both facilities' costs and annual-review income.
    combined = by_key[('ponds+lido', '2020/21')]
    assert (round(combined['cost'], 2), round(combined['income'], 2)) == (8.86, 3.38)
    # 2025/26 has swims and a projected income but no published costs.
    assert by_key[('ponds', '2025/26')]['cost'] is None


def test_maintenance_items_are_grouped_by_building() -> None:
    assert city_chart.maintenance_building('Highgate Ponds - Mens Bathing Pond Toilets - ROOF') == "Men's Pond"
    assert city_chart.maintenance_building('Kenwood - Ladies Bathing Pond Building - POOL LIFT') == "Ladies' Pond"
    assert city_chart.maintenance_building('Hampstead Heath - TEST OF ALL INLET/OUT PIPES & VALVES (PONDS)') == (
        'All ponds: infrastructure')


def test_staff_series_estimates_swimming_staff_from_heath_growth() -> None:
    finance = city_chart.FINANCE_DIR
    data = city_chart.staff_series(city_chart.read_rows(finance / 'heath-costs.csv'),
                                   city_chart.read_rows(finance / 'swimming-costs.csv'))
    assert data['heath']['2024/25']['average_headcount'] == 88  # restated value from the later accounts
    assert round(data['shares']['2022/23'], 3) == 0.263
    estimate = data['estimates']['2025/26']
    assert (round(estimate['central'] / 1000), round(estimate['low'] / 1000), round(estimate['high'] / 1000)) == (
        1560, 1325, 1826)
