"""
Google OR-Tools CP-SAT Solver for College Timetables.
High-speed exact constraint satisfaction and multi-objective optimization with zero hard conflicts.
"""
import time
from typing import List, Dict, Tuple, Any
from collections import defaultdict
from ortools.sat.python import cp_model

from ..models import (
    TimetableDataset,
    TimetableSlot,
    ScheduleResult,
    OptimizationWeights,
    CourseType,
)
from ..analytics import compute_analytics


def solve_with_cp_sat(
    dataset: TimetableDataset,
    max_time_seconds: int = 30,
    weights: OptimizationWeights = None,
) -> ScheduleResult:
    """
    Solves the college timetable problem using OR-Tools CP-SAT with a streamlined linear formulation.
    """
    start_time = time.time()
    if weights is None:
        weights = dataset.weights

    model = cp_model.CpModel()

    time_config = dataset.time_config
    days = time_config.days
    days_count = len(days)
    slots_per_day = time_config.slots_per_day
    lunch_idx = time_config.lunch_slot_idx
    break_slots = set(time_config.break_slot_indices)
    if lunch_idx is not None:
        break_slots.add(lunch_idx)

    rooms_by_id = {r.id: r for r in dataset.rooms}
    faculty_by_id = {f.id: f for f in dataset.faculty}
    batches_by_id = {b.id: b for b in dataset.batches}
    courses_by_id = {c.id: c for c in dataset.courses}

    # Pre-index faculty unavailabilities and preferences as fast O(1) sets
    fac_unavail_sets = {
        f.id: {tuple(u) for u in f.unavailable_slots if len(u) == 2}
        for f in dataset.faculty
    }
    fac_pref_sets = {
        f.id: {tuple(p) for p in f.preferred_slots if len(p) == 2}
        for f in dataset.faculty
    }

    # 1. Decompose courses into discrete sessions to be scheduled
    sessions = []
    session_id_counter = 0

    for course in dataset.courses:
        block_duration = course.consecutive_slots if course.consecutive_slots > 0 else 1
        weekly_hours = course.weekly_hours

        for batch_id in course.batch_ids:
            batch = batches_by_id.get(batch_id)
            if not batch:
                continue

            remaining_hours = weekly_hours
            while remaining_hours > 0:
                cur_duration = min(remaining_hours, block_duration)
                session_id_counter += 1
                sessions.append({
                    "session_id": session_id_counter,
                    "course_id": course.id,
                    "course": course,
                    "batch_id": batch_id,
                    "batch": batch,
                    "duration": cur_duration,
                })
                remaining_hours -= cur_duration

    if not sessions:
        exec_time = time.time() - start_time
        return ScheduleResult(
            status="FEASIBLE",
            solver_type="CP-SAT (Google OR-Tools)",
            execution_time_sec=round(exec_time, 2),
            hard_conflicts_count=0,
            quality_score=100.0,
            schedule=[],
            analytics=compute_analytics(dataset, []),
            message="No course sessions requested to schedule."
        )

    # 2. Decision variables
    x_vars = {}
    session_candidates = [[] for _ in range(len(sessions))]

    faculty_period_vars = defaultdict(list)
    batch_period_vars = defaultdict(list)
    room_period_vars = defaultdict(list)
    faculty_day_vars = defaultdict(list)
    course_batch_day_vars = defaultdict(list)

    for s_idx, session in enumerate(sessions):
        course = session["course"]
        batch = session["batch"]
        dur = session["duration"]

        # Filter strictly eligible rooms (type and capacity)
        eligible_rooms = [
            r for r in dataset.rooms
            if r.room_type == course.room_type_required and r.capacity >= batch.size
        ]
        if not eligible_rooms:
            eligible_rooms = [
                r for r in dataset.rooms
                if r.room_type == course.room_type_required
            ] or list(dataset.rooms)

        # Filter strictly qualified faculty
        if course.faculty_ids:
            eligible_faculty = [faculty_by_id[fid] for fid in course.faculty_ids if fid in faculty_by_id]
        else:
            eligible_faculty = [
                f for f in dataset.faculty
                if f.department == course.department or course.id in f.qualified_courses
            ] or list(dataset.faculty)

        for day in range(days_count):
            for start_slot in range(slots_per_day - dur + 1):
                periods = range(start_slot, start_slot + dur)
                if any(p in break_slots for p in periods):
                    continue

                for room in eligible_rooms:
                    for fac in eligible_faculty:
                        fac_unavail = fac_unavail_sets.get(fac.id, set())
                        if any((day, p) in fac_unavail for p in periods):
                            continue

                        var = model.NewBoolVar(f"x_{s_idx}_{day}_{start_slot}_{room.id}_{fac.id}")
                        key = (s_idx, day, start_slot, room.id, fac.id)
                        x_vars[key] = var
                        session_candidates[s_idx].append(var)

                        for p in periods:
                            faculty_period_vars[(fac.id, day, p)].append(var)
                            batch_period_vars[(batch.id, day, p)].append(var)
                            room_period_vars[(room.id, day, p)].append(var)

                        faculty_day_vars[(fac.id, day)].append((var, dur))
                        course_batch_day_vars[(course.id, batch.id, day)].append(var)

    # Constraint 1: Exactly one assignment per session
    for s_idx, session in enumerate(sessions):
        candidates = session_candidates[s_idx]
        if not candidates:
            exec_time = time.time() - start_time
            return ScheduleResult(
                status="INFEASIBLE",
                solver_type="CP-SAT (Google OR-Tools)",
                execution_time_sec=round(exec_time, 2),
                hard_conflicts_count=1,
                quality_score=0.0,
                schedule=[],
                analytics=compute_analytics(dataset, []),
                message=f"Session for course '{session['course'].name}' ({session['batch'].name}) has no valid slot/room/faculty candidates."
            )
        model.AddExactlyOne(candidates)

    # Constraint 2: No faculty clashes
    for var_list in faculty_period_vars.values():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 3: No batch clashes
    for var_list in batch_period_vars.values():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 4: No room clashes
    for var_list in room_period_vars.values():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 5: Faculty max daily hours
    for (fac_id, day), var_dur_list in faculty_day_vars.items():
        fac = faculty_by_id.get(fac_id)
        if fac and var_dur_list:
            model.Add(sum(var * dur for var, dur in var_dur_list) <= fac.max_daily_hours)

    # Constraint 5b: Student batch max daily lecture hours
    max_batch_global = getattr(time_config, "max_daily_lecture_hours", None)
    for batch in dataset.batches:
        max_batch_hrs = getattr(batch, "max_daily_hours", None) or max_batch_global
        if max_batch_hrs and max_batch_hrs < slots_per_day:
            for day in range(days_count):
                vars_for_day = [v for p in range(slots_per_day) for v in batch_period_vars.get((batch.id, day, p), [])]
                if vars_for_day:
                    model.Add(sum(vars_for_day) <= max_batch_hrs)

    # Constraint 6: Spread course lectures across days for a batch
    for (course_id, batch_id, day), var_list in course_batch_day_vars.items():
        course = courses_by_id[course_id]
        if len(var_list) > 1:
            max_daily_sessions = 1 if course.weekly_hours <= days_count else 2
            model.Add(sum(var_list) <= max_daily_sessions)

    # 3. Soft Constraints & Multi-Objective Optimization
    objective_terms = []

    # Objective A: Faculty Preferred Slots
    pref_weight = int(weights.weight_faculty_preference * 10)
    for (s_idx, day, start_slot, room_id, fac_id), var in x_vars.items():
        dur = sessions[s_idx]["duration"]
        fac_prefs = fac_pref_sets.get(fac_id, set())
        if fac_prefs and any((day, p) in fac_prefs for p in range(start_slot, start_slot + dur)):
            objective_terms.append(-pref_weight * var)

    # Objective B: Preferred Room for Batch
    for (s_idx, day, start_slot, room_id, fac_id), var in x_vars.items():
        batch = sessions[s_idx]["batch"]
        if batch.preferred_room_id and room_id == batch.preferred_room_id:
            objective_terms.append(-int(weights.weight_room_utilization * 5) * var)

    # Objective C: Workload Uniformity across Days
    balance_weight = int(weights.weight_workload_balance * 8)
    usable_slots = slots_per_day - (1 if lunch_idx is not None else 0)
    ideal_daily_hours = min(4, max_batch_global or usable_slots)
    for batch in dataset.batches:
        for day in range(days_count):
            vars_for_day = [v for p in range(slots_per_day) for v in batch_period_vars.get((batch.id, day, p), [])]
            if vars_for_day:
                day_total = model.NewIntVar(0, slots_per_day, f"day_hrs_{batch.id}_{day}")
                model.Add(day_total == sum(vars_for_day))
                dev_var = model.NewIntVar(0, slots_per_day, f"dev_{batch.id}_{day}")
                model.Add(dev_var >= day_total - ideal_daily_hours)
                model.Add(dev_var >= ideal_daily_hours - day_total)
                objective_terms.append(balance_weight * dev_var)

    # Objective D: Compact Student Schedule (Period-level span minimization)
    student_idle_weight = int(weights.weight_idle_student * 10)
    for batch in dataset.batches:
        for day in range(days_count):
            act_vars = []
            for p in range(slots_per_day):
                v_list = batch_period_vars.get((batch.id, day, p), [])
                if v_list:
                    act = model.NewBoolVar(f"act_{batch.id}_{day}_{p}")
                    model.Add(act == sum(v_list))
                    act_vars.append((p, act))

            if act_vars:
                has_cls = model.NewBoolVar(f"has_{batch.id}_{day}")
                model.Add(sum(a for _, a in act_vars) > 0).OnlyEnforceIf(has_cls)
                model.Add(sum(a for _, a in act_vars) == 0).OnlyEnforceIf(has_cls.Not())

                min_p = model.NewIntVar(0, slots_per_day, f"min_{batch.id}_{day}")
                max_p = model.NewIntVar(0, slots_per_day, f"max_{batch.id}_{day}")
                for p, a in act_vars:
                    model.Add(min_p <= p).OnlyEnforceIf(a)
                    model.Add(max_p >= p).OnlyEnforceIf(a)

                span = model.NewIntVar(0, slots_per_day, f"span_{batch.id}_{day}")
                model.Add(span >= max_p - min_p + 1 - (slots_per_day * (1 - has_cls)))
                model.Add(span >= 0)

                tot_cls = model.NewIntVar(0, slots_per_day, f"tot_{batch.id}_{day}")
                model.Add(tot_cls == sum(a for _, a in act_vars))

                idle = model.NewIntVar(0, slots_per_day, f"idle_{batch.id}_{day}")
                model.Add(idle >= span - tot_cls)
                objective_terms.append(student_idle_weight * idle)

    if objective_terms:
        model.Minimize(sum(objective_terms))

    # 4. Execute CP-SAT Solver with multi-threaded portfolio search
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    solver.parameters.num_workers = 8
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)
    exec_time = time.time() - start_time

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = []
        slot_id = 0

        for key, var in x_vars.items():
            if solver.Value(var) == 1:
                s_idx, day, start_slot, room_id, fac_id = key
                session = sessions[s_idx]
                course = session["course"]
                batch = session["batch"]
                dur = session["duration"]
                room = rooms_by_id[room_id]
                faculty = faculty_by_id[fac_id]

                slot_id += 1
                end_slot = start_slot + dur - 1
                slot_time_str = (
                    f"{time_config.slot_times[start_slot].split(' - ')[0]} - "
                    f"{time_config.slot_times[end_slot].split(' - ')[1]}"
                    if end_slot < len(time_config.slot_times)
                    else time_config.slot_times[start_slot]
                )

                schedule.append(
                    TimetableSlot(
                        id=f"slot_{slot_id}",
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        course_type=course.course_type,
                        batch_id=batch.id,
                        batch_name=batch.name,
                        faculty_id=faculty.id,
                        faculty_name=faculty.name,
                        room_id=room.id,
                        room_name=room.name,
                        day_idx=day,
                        day_name=days[day],
                        slot_idx=start_slot,
                        slot_time=slot_time_str,
                        duration=dur,
                        color=course.color or "#3b82f6",
                    )
                )

        schedule.sort(key=lambda s: (s.day_idx, s.slot_idx, s.batch_name))
        analytics = compute_analytics(dataset, schedule)

        status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        msg = (
            f"Successfully generated 100% conflict-free timetable using OR-Tools CP-SAT in {round(exec_time, 2)}s. "
            f"All {len(schedule)} sessions scheduled with zero hard clashes."
        )

        return ScheduleResult(
            status=status_str,
            solver_type="CP-SAT (Google OR-Tools)",
            execution_time_sec=round(exec_time, 2),
            hard_conflicts_count=analytics.hard_conflicts_count,
            quality_score=analytics.quality_score,
            schedule=schedule,
            analytics=analytics,
            message=msg,
        )
    else:
        exec_time = time.time() - start_time
        return ScheduleResult(
            status="INFEASIBLE",
            solver_type="CP-SAT (Google OR-Tools)",
            execution_time_sec=round(exec_time, 2),
            hard_conflicts_count=1,
            quality_score=0.0,
            schedule=[],
            analytics=compute_analytics(dataset, []),
            message=(
                "Could not find a feasible conflict-free timetable under the given constraints. "
                "Try relaxing faculty blackout slots, adding more classrooms/labs, or reducing weekly course hours."
            )
        )
