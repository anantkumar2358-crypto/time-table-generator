"""
Conflict auditor, validation engine, and optimization analytics for College Timetables.
Optimized for single-pass O(N) evaluation and instant O(1) set lookups.
"""
from typing import List, Dict, Any, Tuple
import math
from collections import defaultdict
from .models import (
    TimetableDataset,
    TimetableSlot,
    ScheduleAnalytics,
    MetricDetail,
    CourseType,
)


def validate_schedule(dataset: TimetableDataset, schedule: List[TimetableSlot]) -> Tuple[List[str], int]:
    """
    Performs a deep conflict audit on the schedule.
    Returns (conflict_list, hard_conflicts_count).
    """
    conflicts = []
    hard_conflicts = 0

    rooms_by_id = {r.id: r for r in dataset.rooms}
    faculty_by_id = {f.id: f for f in dataset.faculty}
    batches_by_id = {b.id: b for b in dataset.batches}
    courses_by_id = {c.id: c for c in dataset.courses}

    # Pre-index faculty unavailabilities as fast O(1) sets of (day, period)
    fac_unavail_sets = {
        f.id: {tuple(u) for u in f.unavailable_slots if len(u) == 2}
        for f in dataset.faculty
    }

    lunch_idx = dataset.time_config.lunch_slot_idx
    slots_per_day = dataset.time_config.slots_per_day

    # Maps for tracking period occupations: (day, period) -> list of slots
    faculty_period_map = defaultdict(list)
    batch_period_map = defaultdict(list)
    room_period_map = defaultdict(list)

    # Track hours scheduled per (course_id, batch_id) and faculty daily load
    course_batch_hours = defaultdict(int)
    faculty_daily_hours = defaultdict(lambda: defaultdict(int))

    for slot in schedule:
        # Check boundary
        if slot.slot_idx < 0 or slot.slot_idx + slot.duration > slots_per_day:
            conflicts.append(
                f"[BOUNDARY] Course '{slot.course_name}' ({slot.batch_name}) starts at slot {slot.slot_idx} "
                f"with duration {slot.duration}, which exceeds the {slots_per_day} slots limit on {slot.day_name}."
            )
            hard_conflicts += 1

        course_batch_hours[(slot.course_id, slot.batch_id)] += slot.duration
        faculty_daily_hours[slot.faculty_id][slot.day_idx] += slot.duration

        # Period-level checks
        fac_unavail = fac_unavail_sets.get(slot.faculty_id, set())
        for period in range(slot.slot_idx, slot.slot_idx + slot.duration):
            if lunch_idx is not None and period == lunch_idx:
                conflicts.append(
                    f"[LUNCH OVERLAP] Course '{slot.course_name}' ({slot.batch_name}) scheduled during lunch slot {lunch_idx} "
                    f"on {slot.day_name}."
                )
                hard_conflicts += 1

            if (slot.day_idx, period) in fac_unavail:
                fac = faculty_by_id.get(slot.faculty_id)
                fac_name = fac.name if fac else slot.faculty_id
                conflicts.append(
                    f"[FACULTY UNAVAILABLE] Faculty '{fac_name}' is marked unavailable on "
                    f"{slot.day_name} at slot {period} ('{slot.course_name}')."
                )
                hard_conflicts += 1

            faculty_period_map[(slot.faculty_id, slot.day_idx, period)].append(slot)
            batch_period_map[(slot.batch_id, slot.day_idx, period)].append(slot)
            room_period_map[(slot.room_id, slot.day_idx, period)].append(slot)

        # Room Capacity check
        room = rooms_by_id.get(slot.room_id)
        batch = batches_by_id.get(slot.batch_id)
        if room and batch and room.capacity < batch.size:
            conflicts.append(
                f"[CAPACITY OVERFLOW] Room '{room.name}' (Cap: {room.capacity}) is too small for batch '{batch.name}' "
                f"(Size: {batch.size}) during '{slot.course_name}' on {slot.day_name}."
            )
            hard_conflicts += 1

        # Room Type check
        course = courses_by_id.get(slot.course_id)
        if room and course and course.room_type_required != room.room_type:
            conflicts.append(
                f"[ROOM TYPE MISMATCH] Course '{course.name}' requires '{course.room_type_required.value}' "
                f"but assigned room '{room.name}' is '{room.room_type.value}'."
            )
            hard_conflicts += 1

    # Check 1: Faculty clashes (double-booking)
    for (f_id, day, period), slots_in_period in faculty_period_map.items():
        if len(slots_in_period) > 1:
            fac_name = faculty_by_id[f_id].name if f_id in faculty_by_id else f_id
            c_names = ", ".join([f"'{s.course_name}' ({s.batch_name})" for s in slots_in_period])
            day_name = dataset.time_config.days[day] if day < len(dataset.time_config.days) else f"Day {day}"
            conflicts.append(
                f"[FACULTY CLASH] Faculty '{fac_name}' is double-booked on {day_name} period {period} for: {c_names}."
            )
            hard_conflicts += len(slots_in_period) - 1

    # Check 2: Batch clashes (double-booking)
    for (b_id, day, period), slots_in_period in batch_period_map.items():
        if len(slots_in_period) > 1:
            batch_name = batches_by_id[b_id].name if b_id in batches_by_id else b_id
            c_names = ", ".join([f"'{s.course_name}' (Faculty: {s.faculty_name})" for s in slots_in_period])
            day_name = dataset.time_config.days[day] if day < len(dataset.time_config.days) else f"Day {day}"
            conflicts.append(
                f"[BATCH CLASH] Batch '{batch_name}' has overlapping classes on {day_name} period {period}: {c_names}."
            )
            hard_conflicts += len(slots_in_period) - 1

    # Check 3: Room clashes (double-booking)
    for (r_id, day, period), slots_in_period in room_period_map.items():
        if len(slots_in_period) > 1:
            room_name = rooms_by_id[r_id].name if r_id in rooms_by_id else r_id
            c_names = ", ".join([f"'{s.course_name}' ({s.batch_name})" for s in slots_in_period])
            day_name = dataset.time_config.days[day] if day < len(dataset.time_config.days) else f"Day {day}"
            conflicts.append(
                f"[ROOM CLASH] Room '{room_name}' is double-booked on {day_name} period {period} by: {c_names}."
            )
            hard_conflicts += len(slots_in_period) - 1

    # Check 4: Course weekly hour requirements
    for course in dataset.courses:
        for b_id in course.batch_ids:
            sched_hours = course_batch_hours.get((course.id, b_id), 0)
            req_hours = course.weekly_hours
            if sched_hours != req_hours:
                batch_name = batches_by_id[b_id].name if b_id in batches_by_id else b_id
                conflicts.append(
                    f"[HOURS DEFICIT/EXCESS] Course '{course.name}' for batch '{batch_name}' has "
                    f"{sched_hours} hours scheduled out of required {req_hours} hours."
                )
                hard_conflicts += abs(req_hours - sched_hours)

    # Check 5: Faculty max daily hours
    for f_id, daily_map in faculty_daily_hours.items():
        fac = faculty_by_id.get(f_id)
        if fac:
            for day, hrs in daily_map.items():
                if hrs > fac.max_daily_hours:
                    day_name = dataset.time_config.days[day] if day < len(dataset.time_config.days) else f"Day {day}"
                    conflicts.append(
                        f"[FACULTY WORKLOAD OVERLOAD] Faculty '{fac.name}' is scheduled for {hrs} hours on "
                        f"{day_name}, exceeding maximum permitted {fac.max_daily_hours} hours/day."
                    )
                    hard_conflicts += (hrs - fac.max_daily_hours)

    return conflicts, hard_conflicts


def compute_analytics(dataset: TimetableDataset, schedule: List[TimetableSlot]) -> ScheduleAnalytics:
    """
    Computes in-depth optimization metrics and quality score in a single streamlined pass.
    """
    conflicts, hard_conflicts_count = validate_schedule(dataset, schedule)

    days_count = len(dataset.time_config.days)
    slots_per_day = dataset.time_config.slots_per_day
    lunch_idx = dataset.time_config.lunch_slot_idx

    faculty_by_id = {f.id: f for f in dataset.faculty}
    batches_by_id = {b.id: b for b in dataset.batches}
    rooms_by_id = {r.id: r for r in dataset.rooms}

    # Pre-index preferred slots as fast sets
    fac_pref_sets = {
        f.id: {tuple(p) for p in f.preferred_slots if len(p) == 2}
        for f in dataset.faculty
    }

    # Single-pass collectors
    batch_day_occupied = defaultdict(lambda: defaultdict(set))
    fac_day_occupied = defaultdict(lambda: defaultdict(set))
    room_occupied_hours = defaultdict(int)
    room_capacity_ratios = []
    total_slots_scheduled = 0
    preferred_slots_met = 0
    total_slots_with_pref_target = 0

    for slot in schedule:
        dur = slot.duration
        total_slots_scheduled += dur
        room_occupied_hours[slot.room_id] += dur

        # Room capacity efficiency
        room = rooms_by_id.get(slot.room_id)
        batch = batches_by_id.get(slot.batch_id)
        if room and batch and room.capacity > 0:
            ratio = min(1.0, batch.size / room.capacity)
            room_capacity_ratios.append(ratio * dur)

        # Faculty preferences
        fac_prefs = fac_pref_sets.get(slot.faculty_id, set())
        if fac_prefs:
            total_slots_with_pref_target += dur
            for p in range(slot.slot_idx, slot.slot_idx + dur):
                if (slot.day_idx, p) in fac_prefs:
                    preferred_slots_met += 1

        # Period sets for idle gap analysis
        for p in range(slot.slot_idx, slot.slot_idx + dur):
            batch_day_occupied[slot.batch_id][slot.day_idx].add(p)
            fac_day_occupied[slot.faculty_id][slot.day_idx].add(p)

    # 1. Batch Idle Gaps Analysis
    batch_idle_gaps_total = 0
    batch_stats = {}
    for batch in dataset.batches:
        b_idle = 0
        daily_hours = []
        for day in range(days_count):
            periods = sorted(list(batch_day_occupied[batch.id][day]))
            daily_hours.append(len(periods))
            if len(periods) >= 2:
                min_p, max_p = periods[0], periods[-1]
                for p in range(min_p, max_p + 1):
                    if p not in periods and p != lunch_idx:
                        b_idle += 1
        batch_idle_gaps_total += b_idle
        batch_stats[batch.id] = {
            "name": batch.name,
            "department": batch.department,
            "idle_gap_hours": b_idle,
            "total_weekly_hours": sum(daily_hours),
            "daily_hours": daily_hours,
        }

    avg_batch_idle = batch_idle_gaps_total / max(1, len(dataset.batches))

    # 2. Faculty Idle Gaps Analysis
    faculty_workloads = {}
    total_faculty_idle = 0
    for fac in dataset.faculty:
        f_idle = 0
        daily_hours = []
        for day in range(days_count):
            periods = sorted(list(fac_day_occupied[fac.id][day]))
            daily_hours.append(len(periods))
            if len(periods) >= 2:
                min_p, max_p = periods[0], periods[-1]
                for p in range(min_p, max_p + 1):
                    if p not in periods and p != lunch_idx:
                        f_idle += 1
        total_faculty_idle += f_idle
        faculty_workloads[fac.id] = {
            "name": fac.name,
            "department": fac.department,
            "designation": fac.designation,
            "idle_gap_hours": f_idle,
            "total_weekly_hours": sum(daily_hours),
            "daily_hours": daily_hours,
            "max_daily_hours": fac.max_daily_hours,
        }

    avg_fac_idle = total_faculty_idle / max(1, len(dataset.faculty))

    # 3. Workload Balance Standard Deviation (Batches)
    all_daily_hours = []
    for b_info in batch_stats.values():
        all_daily_hours.extend(b_info["daily_hours"])

    if all_daily_hours:
        mean_hrs = sum(all_daily_hours) / len(all_daily_hours)
        variance = sum((h - mean_hrs) ** 2 for h in all_daily_hours) / len(all_daily_hours)
        daily_std_dev = math.sqrt(variance)
    else:
        daily_std_dev = 0.0

    # 4. Room Utilization Rate & Capacity Efficiency
    usable_periods_per_day = slots_per_day - (1 if lunch_idx is not None else 0)
    total_available_room_hours = len(dataset.rooms) * days_count * usable_periods_per_day

    total_room_occupied = sum(room_occupied_hours.values())
    room_utilization_rate = (total_room_occupied / max(1, total_available_room_hours)) * 100.0

    avg_capacity_efficiency = (
        (sum(room_capacity_ratios) / max(1, total_slots_scheduled)) * 100.0
        if total_slots_scheduled > 0 else 0.0
    )

    room_occupancy = {}
    room_max_hrs = days_count * usable_periods_per_day
    for r in dataset.rooms:
        hrs = room_occupied_hours[r.id]
        room_occupancy[r.id] = {
            "name": r.name,
            "type": r.room_type.value,
            "capacity": r.capacity,
            "occupied_hours": hrs,
            "max_available_hours": room_max_hrs,
            "utilization_percent": round((hrs / max(1, room_max_hrs)) * 100.0, 1),
        }

    # 5. Faculty Preference Satisfaction %
    if total_slots_with_pref_target > 0:
        pref_satisfaction_pct = (preferred_slots_met / total_slots_with_pref_target) * 100.0
    else:
        pref_satisfaction_pct = 100.0

    # 6. Overall Quality Score (0 - 100)
    base_score = 100.0
    if hard_conflicts_count > 0:
        base_score -= min(100.0, hard_conflicts_count * 20.0)

    idle_penalty = (avg_batch_idle * 2.5) + (avg_fac_idle * 1.5)
    variance_penalty = daily_std_dev * 2.0
    pref_bonus = (pref_satisfaction_pct / 100.0) * 5.0

    quality_score = max(0.0, min(100.0, base_score - idle_penalty - variance_penalty + pref_bonus))
    quality_score = round(quality_score, 1)

    def get_status(score, high_is_good=True, thresh_good=75, thresh_warn=50):
        if high_is_good:
            if score >= thresh_good:
                return "excellent"
            elif score >= thresh_warn:
                return "good"
            return "warning"
        else:
            if score <= thresh_warn:
                return "excellent"
            elif score <= thresh_good:
                return "good"
            return "warning"

    metrics_breakdown = {
        "hard_conflicts": MetricDetail(
            value=float(hard_conflicts_count),
            unit="clashes",
            status="excellent" if hard_conflicts_count == 0 else "danger",
            description="Number of critical constraint violations (must be 0 for conflict-free operation)."
        ),
        "batch_idle_time": MetricDetail(
            value=round(avg_batch_idle, 2),
            unit="hrs/batch/wk",
            status=get_status(avg_batch_idle, high_is_good=False, thresh_good=3.0, thresh_warn=1.5),
            description="Average unproductive free periods (gaps) between classes for student batches."
        ),
        "faculty_idle_time": MetricDetail(
            value=round(avg_fac_idle, 2),
            unit="hrs/faculty/wk",
            status=get_status(avg_fac_idle, high_is_good=False, thresh_good=3.0, thresh_warn=1.5),
            description="Average gaps between assigned teaching periods for professors and lecturers."
        ),
        "room_utilization": MetricDetail(
            value=round(room_utilization_rate, 1),
            unit="%",
            status=get_status(room_utilization_rate, high_is_good=True, thresh_good=65.0, thresh_warn=45.0),
            description="Percentage of available classroom and laboratory time actively in use."
        ),
        "capacity_efficiency": MetricDetail(
            value=round(avg_capacity_efficiency, 1),
            unit="%",
            status=get_status(avg_capacity_efficiency, high_is_good=True, thresh_good=70.0, thresh_warn=50.0),
            description="Average ratio of enrolled students to assigned room capacity."
        ),
        "faculty_preferences": MetricDetail(
            value=round(pref_satisfaction_pct, 1),
            unit="%",
            status=get_status(pref_satisfaction_pct, high_is_good=True, thresh_good=80.0, thresh_warn=60.0),
            description="Percentage of assigned classes scheduled in instructors' preferred time windows."
        ),
        "workload_uniformity": MetricDetail(
            value=round(daily_std_dev, 2),
            unit="std dev",
            status=get_status(daily_std_dev, high_is_good=False, thresh_good=1.5, thresh_warn=0.8),
            description="Spread of daily study load across the week. Lower means more evenly balanced."
        )
    }

    return ScheduleAnalytics(
        quality_score=quality_score,
        hard_conflicts_count=hard_conflicts_count,
        total_slots_scheduled=total_slots_scheduled,
        batch_idle_hours_per_week=round(avg_batch_idle, 2),
        faculty_idle_hours_per_week=round(avg_fac_idle, 2),
        room_utilization_rate=round(room_utilization_rate, 1),
        average_capacity_efficiency=round(avg_capacity_efficiency, 1),
        faculty_preference_satisfaction=round(pref_satisfaction_pct, 1),
        daily_workload_std_dev=round(daily_std_dev, 2),
        metrics_breakdown=metrics_breakdown,
        conflict_list=conflicts,
        faculty_workloads=faculty_workloads,
        room_occupancy=room_occupancy,
        batch_stats=batch_stats,
    )
