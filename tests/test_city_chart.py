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
