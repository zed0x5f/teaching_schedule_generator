from dataclasses import dataclass
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import random


@dataclass
class StationRule:
    min: int = 1
    max: int = 6
    required: bool = False
    fill_priority: int = 10


# ---------- Core scheduling ----------


def build_schedule(
    groups: List[str],
    stations: List[str],
    days: int,
    slots_per_day: int,
    station_rules: Dict[str, StationRule],
    strict_required: bool = False,
) -> Tuple[
    List[list[Dict[str, Optional[str]]]], Dict[str, int], Dict[str, Dict[str, int]]
]:
    """
    Build a schedule [day][slot] -> {station: group or None}
    Enforces:
      - per-slot uniqueness: a group can only be used once per slot across all stations
      - per-day per-station uniqueness: a group can visit the same station at most once in a day
      - weekly per-station max caps
      - fairness: prefer groups with lower total assignments
      - min quota bias: prefer groups that are most behind on a station's min
      - required/strict behavior: if no candidate fits, leave None (strict) or allow exceeding max cap only (non-strict)
        NOTE: override never breaks per-slot/per-day-per-station uniqueness.
    """
    # Prepare structures
    schedule = [
        [{s: None for s in stations} for _ in range(slots_per_day)] for _ in range(days)
    ]
    total_assignments = defaultdict(int)  # weekly total per group (fairness)
    station_counts_week = {
        g: defaultdict(int) for g in groups
    }  # weekly per-station per-group
    # per-day per-station counts (to enforce "no more than once per day at same station")
    per_day_station_counts = [
        {g: defaultdict(int) for g in groups} for _ in range(days)
    ]

    def resort():
        return sorted(
            stations,
            key=lambda st: (
                not station_rules[st].required,  # required stations first
                random.randint(1, 100) * (1 / station_rules[st].fill_priority),
            ),  # higher priority first
        )

    ordered_stations = resort()

    def candidate_groups(station: str, day: int, used_in_slot: set) -> List[str]:
        """Return feasible candidates respecting all hard rules (except max when overridden)."""
        max_cap: int = station_rules[station].max
        required = station_rules[station].required

        # First pass: all rules including max caps
        cands = [
            g
            for g in groups
            if g not in used_in_slot
            and per_day_station_counts[day][g][station] == 0
            and station_counts_week[g][station] < max_cap
        ]
        if cands:
            return cands

        # If none and required and NOT strict: allow exceeding weekly max cap
        if required and not strict_required:
            cands = [
                g
                for g in groups
                if g not in used_in_slot
                and per_day_station_counts[day][g][station] == 0
            ]
            # If still none, we must leave empty (e.g., not enough groups to fill stations)
            return cands

        # strict or not required: leave empty if none feasible
        return []

    def choose_group(cands: List[str], station: str) -> Optional[str]:
        """Choose group by (most behind on min quota) -> (least total assignments) -> (least this-station count)."""
        if not cands:
            return None
        min_quota = station_rules[station].min
        # deficit = how many more needed to reach min
        def_key = lambda g: (
            -(
                max(0, min_quota - station_counts_week[g][station])
            ),  # larger deficit first
            total_assignments[g],  # fairness
            station_counts_week[g][station],  # spread within station
            g,  # stable tie-break
        )
        return min(cands, key=def_key)

    # Build schedule day by day, slot by slot
    for d in range(days):
        ordered_stations = resort()
        for s in range(slots_per_day):
            used_in_slot = set()  # enforce "once per slot"
            for st in ordered_stations:
                cands = candidate_groups(st, d, used_in_slot)
                g = choose_group(cands, st)
                if g is not None:
                    schedule[d][s][st] = g  # type: ignore
                    used_in_slot.add(g)
                    total_assignments[g] += 1
                    station_counts_week[g][st] += 1
                    per_day_station_counts[d][g][st] += 1
                else:
                    # If strict_required and no candidate -> leave None
                    # If non-strict and even override can't help -> None (e.g., not enough distinct groups)
                    schedule[d][s][st] = None

    return (
        schedule,  # type: ignore
        dict(total_assignments),
        {g: dict(station_counts_week[g]) for g in groups},
    )


# ---------- Validation helpers (optional but useful) ----------


def validate_schedule(
    schedule: list,
    groups: list,
    stations: list,
    station_rules: dict,
    strict_required: bool = False,
) -> None:
    days = len(schedule)
    slots_per_day = len(schedule[0]) if days else 0

    # 1) No group more than once per slot
    for d in range(days):
        for s in range(slots_per_day):
            assigned = [g for g in (schedule[d][s][st] for st in stations) if g]
            if len(set(assigned)) != len(assigned):
                raise AssertionError(
                    f"Duplicate group within day {d+1}, slot {s+1}: {assigned}"
                )

    # 2) No group same station more than once per day
    for d in range(days):
        counts = {(g, st): 0 for g in groups for st in stations}
        for s in range(slots_per_day):
            for st in stations:
                g = schedule[d][s][st]
                if g:
                    counts[(g, st)] += 1
                    if counts[(g, st)] > 1:
                        raise AssertionError(
                            f"{g} assigned to {st} more than once on day {d+1}"
                        )

    # 3) Required rule honored
    if strict_required:
        for d in range(days):
            for s in range(slots_per_day):
                for st in stations:
                    rule: StationRule = station_rules[st]
                    if rule.required and schedule[d][s][st] is None:
                        raise AssertionError(
                            f"Required station '{st}' left empty on day {d+1}, slot {s+1} in strict mode."
                        )


# ---------- Printing ----------


def print_schedule(
    schedule: List[List[Dict[str, Optional[str]]]],
    stations: List[str],
    groups: List[str],
    total_assignments: Dict[str, int],
    station_counts: Dict[str, Dict[str, int]],
) -> None:
    days = len(schedule)
    slots_per_day = len(schedule[0]) if days else 0

    col_width = max(max(len(st) for st in stations), max(len(g) for g in groups)) + 2
    header = "Slot".ljust(6) + "".join(st.ljust(col_width) for st in stations)
    line = "-" * len(header)

    for d, day in enumerate(schedule, 1):
        print(f"\nDay {d}")
        print(header)
        print(line)
        for slot_idx, slot in enumerate(day, 1):
            row = f"{slot_idx}".ljust(6)
            for st in stations:
                cell = slot[st] if slot[st] else "-"
                row += cell.ljust(col_width) if cell != None else ""
            print(row)

    print("\nTotals per group (week):")
    for g in groups:
        per_station = ", ".join(
            f"{st}={station_counts[g].get(st, 0)}" for st in stations
        )
        print(f"  {g}: {total_assignments.get(g,0)} | {per_station}")


# ---------- Example usage ----------

# if __name__ == "__main__":
#     groups = ["G1", "G2", "G3", "G4"]
#     stations = ["Math", "Science", "Art", "Reading"]
#     station_rules = {
#         "Math": StationRule(min=2, max=4, required=True),
#         "Science": StationRule(min=1, max=3, required=True),
#         "Art": StationRule(min=0, max=2, required=False),
#         "Reading": StationRule(min=2, max=4, required=True),
#     }
#     days = 5
#     slots_per_day = 4
#     strict_required = False  # True => leave required empty if no legal candidate


if __name__ == "__main__":
    groups = ["G1", "G2", "G3", "G4"]

    mary = "mary's station"
    para = "para's station"

    computer = "Computer"

    library = "Library"
    toys = "toys"
    tracing = "tracing"

    stations = [mary, para, computer, library, toys, tracing]

    station_rules = {}
    station_rules[mary] = StationRule(min=3, max=4, required=True)
    station_rules[para] = StationRule(min=3, max=4, required=True)
    station_rules[computer] = StationRule(min=3, max=4, required=True)
    default = StationRule(min=1, max=6, required=False)
    station_rules[library] = default
    station_rules[toys] = default
    station_rules[tracing] = default

    strict_required = False

    schedule, totals, station_counts = build_schedule(
        groups,
        stations,
        # days=
        5,  # days
        3,  # slots
        station_rules,
        strict_required,
    )

    # Optional: validate key invariants; raises AssertionError on violations
    validate_schedule(
        schedule, groups, stations, station_rules, strict_required=strict_required
    )

    print_schedule(schedule, stations, groups, totals, station_counts)
