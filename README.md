# LottoScope

A statistically **honest** lottery analyzer & pick generator.

## The honest part

No algorithm can raise your odds on a fair lottery draw — every combination has identical probability. LottoScope proves this to you on your own data with a **chi-square uniformity test**, then applies the one edge that actually exists: **avoiding popular human patterns** (birthdays ≤31, sequences, visual playslip patterns) so you're less likely to *split* a jackpot if you win. Same win odds, higher expected payout.

## Features

- Pulls real draw history (NY Open Data: Powerball, Mega Millions) or your own CSV; offline demo dataset included
- Frequency (hot/cold), recency ("overdue"), pair co-occurrence, sum-range, odd/even analysis
- Chi-square uniformity test — flags genuinely biased machines, debunks everything else
- Three pick strategies: `smart` (anti-pattern, the real edge), `hot` (frequency-weighted, entertainment), `uniform` (pure random)
- Prints exact jackpot odds per line

## Usage

```bash
python lottery_guesser.py --game powerball --picks 5 --strategy smart
python lottery_guesser.py --game megamillions --picks 5 --strategy hot
python lottery_guesser.py --csv mydata.csv --main-max 49 --bonus-max 10
```

CSV format: `draw_date, n1, n2, n3, n4, n5, bonus` (one draw per line)

No dependencies — stdlib only, Python 3.8+.

## Disclaimer

Hot/cold/overdue numbers have zero predictive power on a fair machine. This tool tells you that, shows you the math, and optimizes for the only thing you can control: not sharing your jackpot.
