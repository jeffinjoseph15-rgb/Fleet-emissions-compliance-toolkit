"""
generate_noon_reports.py
------------------------
Creates a SYNTHETIC (made-up but realistic) year of noon reports for a small
fleet of 3 ships, with deliberate data errors planted in it.

Output files:
  noon_reports.csv  -> the "messy" data you will clean and analyse
  answer_key.csv    -> a list of every error that was planted
                       (don't open this until you have built your own checks!)

All vessels, IMO numbers and values are fictional. Distances are approximate.
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(seed=42)   # fixed seed = same data every time you run it
START_DATE = pd.Timestamp("2025-01-01")
END_DATE = pd.Timestamp("2025-12-31")

# ---------------------------------------------------------------------------
# 1. The fleet (fictional ships)
#    design_speed_kn   = normal service speed
#    me_tpd_at_design  = main engine fuel use, tonnes per day at that speed
#    ae_tpd            = auxiliary engines (electricity), tonnes per day
# ---------------------------------------------------------------------------
FLEET = [
    {"vessel_name": "NORDIC AURORA", "imo_number": 9900011, "vessel_type": "Oil tanker",
     "dwt": 110000, "design_speed_kn": 12.5, "me_tpd_at_design": 34.0, "ae_tpd": 2.5,
     "route": [("Houston", "Rotterdam", 5000), ("Rotterdam", "Gothenburg", 520),
               ("Gothenburg", "Houston", 5200)]},
    {"vessel_name": "FJORD TRADER", "imo_number": 9900023, "vessel_type": "Bulk carrier",
     "dwt": 58000, "design_speed_kn": 12.0, "me_tpd_at_design": 24.0, "ae_tpd": 2.0,
     "route": [("Santos", "Rotterdam", 5400), ("Rotterdam", "Richards Bay", 6600),
               ("Richards Bay", "Santos", 3700)]},
    {"vessel_name": "BALTIC CROWN", "imo_number": 9900035, "vessel_type": "Container ship",
     "dwt": 50000, "design_speed_kn": 16.0, "me_tpd_at_design": 58.0, "ae_tpd": 4.0,
     "route": [("Rotterdam", "Hamburg", 300), ("Hamburg", "Antwerp", 370),
               ("Antwerp", "Algeciras", 1300), ("Algeciras", "New York", 3200),
               ("New York", "Rotterdam", 3350)]},
]


def make_clean_reports(ship):
    """Build one clean noon report per day for one ship."""
    rows = []
    day = START_DATE
    voyage_no = 0
    leg = 0
    while day <= END_DATE:
        from_port, to_port, distance = ship["route"][leg % len(ship["route"])]
        voyage_no += 1
        voyage_id = f"{ship['imo_number']}-V{voyage_no:03d}"

        # --- sea passage ---
        speed = ship["design_speed_kn"] * rng.uniform(0.85, 1.02)
        remaining = distance
        while remaining > 0.5 and day <= END_DATE:
            hours = 24.0
            if rng.random() < 0.04:          # clocks change at sea -> 23 or 25 hour "days" (normal!)
                hours = float(rng.choice([23.0, 25.0]))
            day_speed = speed * rng.uniform(0.93, 1.05)   # weather effect
            if remaining < day_speed * hours:             # arrival day: only part of the day at sea
                hours = max(1.0, round(remaining / day_speed, 1))
            dist_today = min(remaining, day_speed * hours)
            if remaining - dist_today < 40:               # avoid a tiny leftover sea day
                dist_today = remaining
            actual_speed = dist_today / hours
            # fuel use rises roughly with speed cubed ("propeller law")
            me = ship["me_tpd_at_design"] * (actual_speed / ship["design_speed_kn"]) ** 3
            me *= (hours / 24) * rng.uniform(0.95, 1.08)
            ae = ship["ae_tpd"] * (hours / 24) * rng.uniform(0.9, 1.1)
            rows.append({
                "report_date": day.date(), "vessel_name": ship["vessel_name"],
                "imo_number": ship["imo_number"], "vessel_type": ship["vessel_type"],
                "dwt": ship["dwt"], "voyage_id": voyage_id, "report_type": "At Sea",
                "from_port": from_port, "to_port": to_port,
                "hours": hours, "distance_nm": round(dist_today, 1),
                "avg_speed_kn": round(actual_speed, 2),
                "me_fuel_type": "VLSFO", "me_consumption_mt": round(me, 2),
                "ae_fuel_type": "MGO", "ae_consumption_mt": round(ae, 2),
            })
            remaining -= dist_today
            day += pd.Timedelta(days=1)

        # --- port stay at destination ---
        port_days = int(rng.integers(1, 4))
        for _ in range(port_days):
            if day > END_DATE:
                break
            ae = ship["ae_tpd"] * 1.3 * rng.uniform(0.9, 1.1)   # cargo ops use more power
            rows.append({
                "report_date": day.date(), "vessel_name": ship["vessel_name"],
                "imo_number": ship["imo_number"], "vessel_type": ship["vessel_type"],
                "dwt": ship["dwt"], "voyage_id": voyage_id, "report_type": "In Port",
                "from_port": to_port, "to_port": to_port,
                "hours": 24.0, "distance_nm": 0.0, "avg_speed_kn": 0.0,
                "me_fuel_type": "VLSFO", "me_consumption_mt": 0.0,
                "ae_fuel_type": "MGO", "ae_consumption_mt": round(ae, 2),
            })
            day += pd.Timedelta(days=1)
        leg += 1
    return rows


def plant_errors(df):
    """Insert realistic human/data errors and record each one in an answer key."""
    key = []
    sea = df.index[df["report_type"] == "At Sea"].tolist()
    allrows = df.index.tolist()

    def pick(pool, n):
        chosen = rng.choice(pool, size=n, replace=False)
        for i in chosen:          # stop the same row being used twice
            pool.remove(i)
        return chosen

    def log(i, error_type, field, original, new):
        key.append({"report_date": df.at[i, "report_date"], "vessel_name": df.at[i, "vessel_name"],
                    "error_type": error_type, "field": field,
                    "correct_value": original, "value_in_file": new})

    # 1. Consumption entered in kg instead of tonnes (x1000)
    for i in pick(sea, 6):
        o = df.at[i, "me_consumption_mt"]; df.at[i, "me_consumption_mt"] = round(o * 1000, 0)
        log(i, "Unit error (kg instead of tonnes)", "me_consumption_mt", o, df.at[i, "me_consumption_mt"])
    # 2. Typo: extra digit (x10)
    for i in pick(sea, 6):
        o = df.at[i, "me_consumption_mt"]; df.at[i, "me_consumption_mt"] = round(o * 10, 2)
        log(i, "Typo - extra digit", "me_consumption_mt", o, df.at[i, "me_consumption_mt"])
    # 3. Impossible distance (speed far above what the ship can do)
    for i in pick(sea, 5):
        o = df.at[i, "distance_nm"]; df.at[i, "distance_nm"] = float(rng.integers(700, 950))
        log(i, "Impossible distance/speed", "distance_nm", o, df.at[i, "distance_nm"])
    # 4. Negative value
    for i in pick(allrows, 4):
        o = df.at[i, "ae_consumption_mt"]; df.at[i, "ae_consumption_mt"] = -o
        log(i, "Negative value", "ae_consumption_mt", o, -o)
    # 5. Blank (missing) value
    for i in pick(sea, 5):
        o = df.at[i, "me_consumption_mt"]; df.at[i, "me_consumption_mt"] = np.nan
        log(i, "Missing value", "me_consumption_mt", o, "blank")
    # 6. Inconsistent fuel labels (typed by hand)
    for i in pick(sea, 6):
        o = df.at[i, "me_fuel_type"]; new = str(rng.choice(["vlsfo", "VLSF0", "VLS FO", "Vlsfo "]))
        df.at[i, "me_fuel_type"] = new
        log(i, "Inconsistent fuel label", "me_fuel_type", o, new)
    # 7. Hours impossible for one daily report
    for i in pick(sea, 3):
        o = df.at[i, "hours"]; df.at[i, "hours"] = 48.0
        log(i, "Impossible hours", "hours", o, 48.0)

    # 8. Duplicate reports (same day sent twice)
    dup_idx = pick(allrows, 4)
    for i in dup_idx:
        log(i, "Duplicate report", "whole row", "one row", "two identical rows")
    df = pd.concat([df, df.loc[dup_idx]])

    # 9. Missing days (report never sent)
    drop_idx = pick(allrows, 6)
    for i in drop_idx:
        log(i, "Missing day (no report)", "whole row", "row should exist", "row missing")
    df = df.drop(index=drop_idx)

    df = df.sort_values(["vessel_name", "report_date"]).reset_index(drop=True)
    key_df = pd.DataFrame(key).sort_values(["vessel_name", "report_date"]).reset_index(drop=True)
    return df, key_df


if __name__ == "__main__":
    clean = pd.DataFrame([r for ship in FLEET for r in make_clean_reports(ship)])
    messy, answer_key = plant_errors(clean.copy())
    messy.to_csv("noon_reports.csv", index=False)
    answer_key.to_csv("answer_key.csv", index=False)
    print(f"Created noon_reports.csv with {len(messy)} rows for {messy['vessel_name'].nunique()} ships.")
    print(f"Planted {len(answer_key)} errors (see answer_key.csv - peek only when you're ready!).")
