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
