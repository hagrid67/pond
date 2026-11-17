# Cyclical Works Programme (CWP): notes

Working notes on the City Surveyor's Cyclical Works Programme for Hampstead Heath:
planned repairs, maintenance and replacements to buildings and infrastructure. The
data is in [`cwp.csv`](cwp.csv), extracted with
[`scripts/extract-cwp.py`](../scripts/extract-cwp.py), and charted by
`city-chart.py --chart cwp` (pies; see [docs/city-chart.md](../docs/city-chart.md)) and
`--chart maintenance` (swimming buildings only).

## Which lists exist, and are they planned, underway or past?

| List | Committee | Status | Total |
| --- | --- | --- | ---: |
| 2020/21 "Actual List" | Sept 2019 (bid for 2020/21) | **Planned** for 2020/21. Some items reappear later (below), so not all were done. | £778,200 |
| 2021/22 deferred list | Feb 2021 ("CWP 2021/22 Updated Bid Report", Appendix A) | **Not funded** in 2021/22: deferred to later bids after Covid savings cut the Open Spaces bid from £1.60m to £0.43m | £187,300 |
| 2021/22 reserve list | Feb 2021 (same appendix) | **Not funded**; a reserve list. It covers more than the Heath, which is why Misc is £1.6m | £2,008,000 |
| 2026/27 project list | Feb 2026 (Appendix 3 to the 2026/27 Revenue & Capital Budgets) | **Planned** for April 2026 – March 2027, so **underway now** (Nov 2026). Year 3 of the City Surveyor's five-year programme. | £1,510,000 |

- **Not actual spend:** none of these lists record what was actually spent.
- **Lists for 2022/23 to 2025/26:** none were found in the committee papers.
- **Five-year programme:** from 2024/25 the CWP is a rolling five-year programme
  ("City Estate CWP"). The May 2025 "Year 1 Overview" (July 2025 papers,
  `2025-0716/06-s221055`, mostly charts read by OCR) gives:
  - **Year 1:** City Estate-wide forecast £2.69m against £3.11m actual spend.
  - **Years 2–5:** project-by-project forecasts. Year 3 matches the 2026/27 list
    (e.g. Lily Pond survey £55k; pipes and valves £25.5k vs £26k).
  - **Year 2 (2025/26) swimming items:**
    - Lido fire alarm, £55k;
    - Lido fabric repairs, £36k;
    - desilting of all ponds, £90k;
    - "Minor refurbishment of Pond Facility", £125k (Kenwood area, presumably the
      Ladies' Pond).
- **Progress reports:** the City Surveyor's quarterly CWP updates to the committee
  (March, May and September 2026) are pictures with no readable item detail.
- **Actual CWP spend:** this appears only as totals and variances in the outturn
  reports, e.g.:
  - 2025/26: CWP £3.57m against a £3.35m final budget;
  - 2024/25: Men's Pond jetty repairs £32k and Ladies' Pond showers/kitchen £57k
    cited as CWP spend.

## 2026/27 by site (`charts/cwp-2026-27.png`)

| Site | £k | Share | Main items |
| --- | ---: | ---: | --- |
| Lido (incl. café) | 510 | 34% | Landlord's lighting & power rewire 180; fire alarm (info centre) 55; decorations 50; flooring 36; roller shutters 25; café interior 23; roof 22 |
| General/Infrastructure | 221 | 15% | Main water supply pipework 75; Golders Hill Lily Pond survey/dredging 55; bandstands/shelters 55; pond pipes & valves test 26 |
| Misc | 203 | 13% | Parliament Hill path resurfacing 90; Kenwood Yard drainage 50; Vale of Health fencing 30; West Heath drainage survey 18 |
| Golders Hill Park | 172 | 11% | Drainage 54; staff yard windows 36 + 6; flooring 15 |
| Athletics Track | 154 | 10% | Pavilion walls/ceilings/floors 55; men's toilets 25 |
| Playground | 104 | 7% | Paddling pool resurface 96 |
| Bowling Green | 71 | 5% | Pavilion roofs, decorations, kitchen, toilets |
| Men's Pond | 49 | 3% | Changing enclosure decorations 20; Life Buoys kitchen 8; toilet roof 6 |
| Football Changing Rooms | 14 | 1% | Decorations |
| Ladies' Pond | 12 | 1% | Pool lift 12 |
| Mixed Pond | 0 | – | No items |

Swimming sites together: £571k (38%), almost all at the Lido.

Site assignment is by keywords in the item names (`CWP_SITES` in `city-chart.py`):
- **"Highgate Ponds" items** count as Men's Pond.
- **Items not matched to a named site** (Parliament Hill paths, Kenwood, Vale of
  Health, West Heath, Hampstead Ponds survey, Whitestone Pond) go to Misc.

## Items that keep coming back

| Item | 2020/21 actual list | 2021/22 deferred/reserve | Later |
| --- | --- | --- | --- |
| Lido fire alarm (info centre) | £36,000 | £36,100 (deferred) | £55,000 (Year 2 forecast, and again in 2026/27) |
| Lido landlord's lighting & power rewire | – | £30,000 (reserve) | £180,000 (2026/27) |
| Lido roller shutters (8) | – | £15,500 (deferred) | £25,000 (2026/27) |
| Lido decorations | – | £15,000 (reserve) | £12,000 (2026/27) |
| Highgate Ponds drainage overhaul | £50,000 | £50,000 (reserve) | – |
| Men's Pond changing enclosure decorations | – | £15,000 (reserve) | £20,000 (2026/27) |
| Mixed Pond fencing | – | £20,000 (deferred) | – (not in 2026/27) |

The Lido items deferred in 2021 have grown substantially in cost by 2026/27. The
rewire is now six times the 2021 figure, which may also reflect a larger scope.

## Men's Pond jetty and diving board

| Date | Source | What it says |
| --- | --- | --- |
| Sept 2019 | CWP 2020/21 actual list | "Highgate Ponds – Jetty & decking overhaul" £20,000 |
| Mar 2020 | Swimming Review, Appendix 3 (projects), item 22 | "Design and fabricate a cover to securely close the diving board when the Men's Bathing Pond is reaching the peak bathing load" |
| Jun 2020 – Feb 2021 | Covid swimming arrangements | No access to the diving board; trial re-installation in winter 2020/21 |
| Feb 2025 | Sports & Wellbeing Forum minutes (p2) | Diving board "out of action due to issues at the jetty with various items failing, including the concrete, slabs, steps and handrail". Two quotes obtained; "not within the reactive works budget", so internal funding sought through a competitive bid process |
| Feb 2025 | Assistant Director's report (p8) | Jetty repairs scheduled for spring 2025, including "reinstallation of the much-loved and popular diving board" |
| May 2025 | Assistant Director's report (p7) | New concrete base at the end of the jetty, "diving board recured in place", handrails replaced, slabs re-laid |
| Jul 2025 | Assistant Director's report; 2024/25 outturn (p3) | Jetty refurbished and diving board reinstated; "repairs at Men's Pond Jetty (£32,000)" counted as CWP spend in 2024/25 |
| Feb 2026 | Assistant Director's report (p14) | "Main jetty repairs were completed in November and the diving board will be repaired and reinstated in January 2026" |
| May 2026 | Assistant Director's report (p8) | "The diving board was also repaired and reinstated in January 2026. More robust fixings have now been installed to secure the diving board onto the jetty." |

The papers don't give a separate cost for the diving board itself. The Ladies'
Pond had a temporary diving ban in spring 2026 because of objects thrown in by
trespassers. A diving company swept all three ponds on 6–7 May 2026 at an
unbudgeted £5,500.

## Men's Pond showers and changing space

The February 2026 report said the public showers, toilets and changing space at the
Men's Pond would be refurbished in early 2026 under the CWP. In May 2026 this was
moved to autumn 2026, after the peak season. It doesn't appear as a separate line
in the 2026/27 list, which has only decorations, kitchen and toilet roof items for
the Men's Pond, so it is probably funded from an earlier CWP year.
