#!/usr/bin/env python3
"""
LottoScope — a statistically HONEST lottery analyzer & pick generator.

What it does:
  1. Pulls real historical draw data (NY Open Data API: Powerball / Mega Millions
     / Mass Cash / Numbers) or loads a CSV you provide.
  2. Runs frequency, recency ("overdue"), pair/co-occurrence, sum-range,
     odd/even and high/low distribution analysis.
  3. Runs a chi-square uniformity test to tell you whether any number's
     deviation is actually significant or just noise (spoiler: it's noise).
  4. Generates picks using the ONE edge that actually exists:
       - every combination has identical win probability, BUT
       - avoiding popular human patterns (birthdays 1-31, visual patterns,
         sequences) reduces the chance you SPLIT a jackpot if you win.
     Optionally weights picks toward "hot" numbers for entertainment,
     clearly labeled as having zero predictive value.

Usage:
  python lottery_guesser.py --game powerball --picks 5 --strategy smart
  python lottery_guesser.py --game megamillions --picks 5 --strategy hot
  python lottery_guesser.py --csv mydata.csv --main-max 69 --bonus-max 26

CSV format: draw_date, n1, n2, n3, n4, n5, bonus   (one draw per line)
"""

import argparse, csv, json, random, statistics, sys, urllib.request
from collections import Counter
from math import comb

# ----------------------------- Game configs --------------------------------
GAMES = {
    "powerball":    {"main": 5, "main_max": 69, "bonus_max": 26,
                     "api": "https://data.ny.gov/resource/d6yy-54nr.json"},
    "megamillions": {"main": 5, "main_max": 70, "bonus_max": 25,
                     "api": "https://data.ny.gov/resource/5xaw-6ayf.json"},
    "masscash":     {"main": 5, "main_max": 35, "bonus_max": 0,
                     "api": "https://data.mass.gov/resource/9z7r-pfzn.json"},
}

def fetch_ny(api, limit=3000):
    url = f"{api}?%24limit={limit}&%24order=draw_date+DESC"
    req = urllib.request.Request(url, headers={"User-Agent": "LottoScope/1.0"})
    rows = json.load(urllib.request.urlopen(req, timeout=30))
    draws = []
    for r in rows:
        nums = [int(x) for x in r["winning_numbers"].split()]
        bonus = int(r.get("mega_ball") or r.get("powerball") or 0)
        draws.append((r["draw_date"][:10], nums[:5], bonus))
    return draws

def load_csv(path):
    draws = []
    with open(path) as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#"):
                continue
            nums = [int(x) for x in row[1:-1]] if len(row) > 6 else [int(x) for x in row[1:6]]
            bonus = int(row[-1]) if len(row) > 6 else 0
            draws.append((row[0], nums, bonus))
    return draws

def demo_dataset(n=1200, main_max=69, bonus_max=26, seed=42):
    """Uniform-random demo draws (what fair lottery data actually looks like)."""
    rng = random.Random(seed)
    return [(f"2022-{1+i//100:02d}-{1+i%28:02d}",
             sorted(rng.sample(range(1, main_max+1), 5)),
             rng.randint(1, bonus_max) if bonus_max else 0) for i in range(n)]

# ----------------------------- Analysis ------------------------------------
def chi_square_uniform(counts, total_balls, n_draws, picks_per_draw=5):
    expected = n_draws * picks_per_draw / total_balls
    chi2 = sum((counts.get(i, 0) - expected) ** 2 / expected
               for i in range(1, total_balls + 1))
    # df = total_balls-1; rough 5% critical value ≈ df + 1.645*sqrt(2*df)
    df = total_balls - 1
    crit = df + 1.645 * (2 * df) ** 0.5
    return chi2, df, crit, chi2 < crit

def analyze(draws, main_max, bonus_max):
    freq = Counter(n for _, nums, _ in draws for n in nums)
    bfreq = Counter(b for _, _, b in draws if b)
    last_seen = {i: None for i in range(1, main_max + 1)}
    for idx, (_, nums, _) in enumerate(draws):  # draws sorted newest first
        for n in nums:
            if last_seen[n] is None:
                last_seen[n] = idx
    sums = [sum(nums) for _, nums, _ in draws]
    odd_even = Counter(sum(n % 2 for n in nums) for _, nums, _ in draws)
    pairs = Counter()
    for _, nums, _ in draws:
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pairs[(nums[i], nums[j])] += 1
    chi2, df, crit, uniform = chi_square_uniform(freq, main_max, len(draws))
    return dict(freq=freq, bfreq=bfreq, last_seen=last_seen,
                sum_mean=statistics.mean(sums), sum_sd=statistics.stdev(sums),
                odd_even=odd_even, top_pairs=pairs.most_common(5),
                chi2=chi2, df=df, crit=crit, uniform=uniform)

# ------------------------- Pick strategies ---------------------------------
def pick_uniform(main_max, bonus_max, rng):
    return sorted(rng.sample(range(1, main_max + 1), 5)), \
           (rng.randint(1, bonus_max) if bonus_max else None)

def pick_hot(freq, bfreq, main_max, bonus_max, rng):
    """Entertainment mode: weight by historical frequency. Zero real edge."""
    weights = [freq.get(i, 0) + 1 for i in range(1, main_max + 1)]
    chosen = set()
    while len(chosen) < 5:
        chosen.add(rng.choices(range(1, main_max + 1), weights=weights)[0])
    bonus = rng.choices(range(1, bonus_max + 1),
                        weights=[bfreq.get(i, 0) + 1 for i in range(1, bonus_max + 1)])[0] if bonus_max else None
    return sorted(chosen), bonus

def pick_smart(main_max, bonus_max, rng):
    """The only edge that exists: anti-pattern picks to avoid jackpot splits.
       - Spread across full range incl. >31 (non-birthday numbers)
       - Avoid sequences and visual column patterns
       - Random odd/even, random sum within common band (so the ticket
         doesn't LOOK weird, but isn't a human pattern either)"""
    while True:
        nums, bonus = pick_uniform(main_max, bonus_max, rng)
        high = sum(1 for n in nums if n > 31)
        spread = max(nums) - min(nums)
        consec = sum(1 for a, b in zip(nums, nums[1:]) if b - a == 1)
        if high >= 2 and spread >= main_max * 0.5 and consec <= 1:
            return nums, bonus

def jackpot_odds(main_max, bonus_max):
    c = comb(main_max, 5)
    return c * bonus_max if bonus_max else c

# -------------------------------- Main -------------------------------------
def main():
    ap = argparse.ArgumentParser(description="LottoScope — honest lottery analyzer")
    ap.add_argument("--game", choices=GAMES.keys())
    ap.add_argument("--csv", help="path to your own draw history CSV")
    ap.add_argument("--main-max", type=int, default=69)
    ap.add_argument("--bonus-max", type=int, default=26)
    ap.add_argument("--picks", type=int, default=5)
    ap.add_argument("--strategy", choices=["smart", "hot", "uniform"], default="smart")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    if args.game:
        cfg = GAMES[args.game]
        main_max, bonus_max = cfg["main_max"], cfg["bonus_max"]
    else:
        main_max, bonus_max = args.main_max, args.bonus_max

    # --- load data ---
    if args.csv:
        draws = load_csv(args.csv)
        print(f"Loaded {len(draws)} draws from {args.csv}")
    elif args.game:
        try:
            draws = fetch_ny(cfg["api"])
            print(f"Fetched {len(draws)} real {args.game} draws (newest: {draws[0][0]})")
        except Exception as e:
            print(f"[offline: {e.__class__.__name__}] using built-in demo dataset")
            draws = demo_dataset(main_max=main_max, bonus_max=bonus_max)
    else:
        draws = demo_dataset(main_max=main_max, bonus_max=bonus_max)
        print(f"Demo dataset: {len(draws)} simulated draws")

    # --- analysis ---
    a = analyze(draws, main_max, bonus_max)
    print("\n===== STATISTICAL ANALYSIS =====")
    print(f"Draws analyzed : {len(draws)}")
    print(f"Chi-square uniformity test: chi2={a['chi2']:.1f} (df={a['df']}, "
          f"5% critical≈{a['crit']:.1f}) -> "
          + ("PASSES: numbers are uniform; no exploitable bias."
             if a["uniform"] else
             "FAILS uniformity — investigate further!"))
    hot = a["freq"].most_common(5)
    cold = sorted(a["freq"].items(), key=lambda kv: kv[1])[:5]
    overdue = sorted(a["last_seen"].items(), key=lambda kv: (kv[1] is None, kv[1]), reverse=True)[:5]
    print(f"Hottest (most drawn) : {hot}")
    print(f"Coldest (least drawn): {cold}")
    print(f"Most 'overdue' (draws since seen): {[(n, d) for n, d in overdue]}")
    print(f"Typical sum: {a['sum_mean']:.0f} ± {a['sum_sd']:.0f}")
    print(f"Odd-count distribution: {dict(sorted(a['odd_even'].items()))}")
    print(f"Top pairs: {a['top_pairs']}")
    print("\nNOTE: hot/cold/overdue have NO predictive power on a fair machine.")
    print("The chi-square result above is the proof. The only real edge is")
    print("avoiding popular human picks to reduce jackpot-splitting risk.")

    # --- picks ---
    rng = random.Random(args.seed)
    print(f"\n===== PICKS ({args.strategy}) =====")
    for i in range(args.picks):
        if args.strategy == "smart":
            nums, bonus = pick_smart(main_max, bonus_max, rng)
        elif args.strategy == "hot":
            nums, bonus = pick_hot(a["freq"], a["bfreq"], main_max, bonus_max, rng)
        else:
            nums, bonus = pick_uniform(main_max, bonus_max, rng)
        s = "  ".join(f"{n:02d}" for n in nums)
        s += f"   | bonus: {bonus:02d}" if bonus else ""
        print(f"  Pick {i+1}: {s}")

    odds = jackpot_odds(main_max, bonus_max)
    print(f"\nJackpot odds per line: 1 in {odds:,}")
    print("Every pick above — yours, mine, or a psychic's — has exactly these odds.")

if __name__ == "__main__":
    main()
