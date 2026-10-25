import csv
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse


def test_official_historical_pond_fees_and_provenance() -> None:
    path = Path(__file__).resolve().parents[1] / 'prices' / 'pond-fees.csv'
    with path.open(encoding='utf-8', newline='') as source:
        rows = list(csv.DictReader(source))

    assert [int(row['year']) for row in rows] == list(range(2005, 2028))
    expected_season_prices = {
        2011: ('110.00', '55.00'),
        2012: ('115.00', '60.00'),
        2013: ('118.50', '62.00'),
        2014: ('121.50', '63.50'),
        2015: ('125.00', '66.00'),
        2016: ('125.00', '66.00'),
        2017: ('125.00', '66.00'),
        2018: ('125.00', '66.00'),
    }
    for row in rows:
        year = int(row['year'])
        if year in expected_season_prices:
            adult, concession = expected_season_prices[year]
            assert Decimal(row['adult_season_12m_gbp']) == Decimal(adult)
            assert Decimal(row['concession_season_12m_gbp']) == Decimal(concession)
            assert Decimal(row['adult_payg_gbp']) == Decimal('2.00')
            assert Decimal(row['concession_payg_gbp']) == Decimal('1.00')
            assert row['status'] == 'official_verified'
            assert row['effective_from'] == f'{year}-04-01'
            source_url = urlparse(row['source_url'])
            assert source_url.scheme == 'https'
            assert source_url.netloc == 'democracy.cityoflondon.gov.uk'
            assert source_url.path.endswith('.pdf')
            assert source_url.fragment in {'page=3', 'page=5'}
        else:
            assert row['status'] != 'official_verified'
            assert not row['source_url']
            assert not row['effective_from']
        if year == 2018:
            assert row['approval_url'] == (
                'https://democracy.cityoflondon.gov.uk/mgAi.aspx?ID=66661'
            )
        if year <= 2010:
            assert row['status'] == 'historical_assumption'
            assert Decimal(row['adult_season_12m_gbp']) == Decimal('110.00')
            assert Decimal(row['concession_season_12m_gbp']) == Decimal('55.00')
