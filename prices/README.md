# Bathing ponds fee data

`pond-fees.csv` stores the adult and concession PAYG and 12-month season-ticket
prices used by `scripts/price-chart.py`. Each year is the May price/index
comparison point; the 2027 row is proposed, not an observed tariff.

The 2005-2019 values are carried back from the supplied 2018/19 prices as a
historical assumption, as requested. They are marked `historical_assumption`
and should not be treated as independently verified tariffs. Later prices are
the values previously supplied for the chart.

The month is not the same for every documented increase. [Time Out reported
that the 2025 increase took effect on 1 April 2025](https://www.timeout.com/london/news/hampstead-heaths-swimming-ponds-are-going-up-in-price-022525).
For the following increase, a [15 May 2026 report](https://www.timeout.com/london/news/prices-have-gone-up-at-four-of-north-londons-most-popular-open-water-swimming-spots-051526)
says the new prices had gone up "this month" but does not give an exact
effective day. The annual chart uses May index observations as requested; it
does not claim all historical price changes took effect in May.
