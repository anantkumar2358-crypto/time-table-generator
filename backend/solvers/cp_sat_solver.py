"""
Google OR-Tools CP-SAT Solver for College Timetables.
Provides exact constraint satisfaction and multi-objective optimization with zero hard conflicts.
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
    Solves the college timetable problem using OR-Tools CP-SAT.
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

    # 1. Decompose courses into discrete sessions to be scheduled
    # Each session represents a contiguous block of duration L
    sessions = []
    session_id_counter = 0

    for course in dataset.courses:
        # Determine duration of blocks
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
        analytics = compute_analytics(dataset, [])
        return ScheduleResult(
            status="FEASIBLE",
            solver_type="CP-SAT (Google OR-Tools)",
            execution_time_sec=round(exec_time, 2),
            hard_conflicts_count=0,
            quality_score=100.0,
            schedule=[],
            analytics=analytics,
            message="No course sessions requested to schedule."
        )

    # 2. Decision variables
    # x[session_idx, day, start_slot, room_id, faculty_id] -> BoolVar
    x_vars = {}
    session_candidates = defaultdict(list)

    # Pre-index candidates for quick constraint formulation
    faculty_period_vars = defaultdict(list)  # (faculty_id, day, period) -> list of var
    batch_period_vars = defaultdict(list)    # (batch_id, day, period) -> list of var
    room_period_vars = defaultdict(list)     # (room_id, day, period) -> list of var
    faculty_day_vars = defaultdict(list)     # (faculty_id, day) -> list of (var, duration)
    batch_day_vars = defaultdict(list)       # (batch_id, day) -> list of (var, start_slot, duration)
    course_batch_day_vars = defaultdict(list) # (course_id, batch_id, day) -> list of var

    # Identify eligible rooms and faculty for each session
    for s_idx, session in enumerate(sessions):
        course = session["course"]
        batch = session["batch"]
        dur = session["duration"]

        # Eligible rooms: matching room type and capacity >= batch size
        eligible_rooms = [
            r for r in dataset.rooms
            if r.room_type == course.room_type_required and r.capacity >= batch.size
        ]
        # Fallback if no room exactly matches capacity: take largest available room of correct type
        if not eligible_rooms:
            eligible_rooms = [
                r for r in dataset.rooms
                if r.room_type == course.room_type_required
            ]
        # Absolute fallback: any room with adequate capacity
        if not eligible_rooms:
            eligible_rooms = [
                r for r in dataset.rooms
                if r.capacity >= batch.size
            ]
        if not eligible_rooms:
            eligible_rooms = list(dataset.rooms)

        # Eligible faculty
        if course.faculty_ids:
            eligible_faculty = [faculty_by_id[fid] for fid in course.faculty_ids if fid in faculty_by_id]
        else:
            eligible_faculty = [
                f for f in dataset.faculty
                if f.department == course.department or course.id in f.qualified_courses
            ]
        if not eligible_faculty:
            eligible_faculty = list(dataset.faculty)

        # Generate candidate assignments (day, start_slot, room, faculty)
        for day in range(days_count):
            for start_slot in range(slots_per_day - dur + 1):
                # Check lunch / break conflict: no period in [start_slot, start_slot + dur) can be a break
                periods = range(start_slot, start_slot + dur)
                if any(p in break_slots for p in periods):
                    continue

                for room in eligible_rooms:
                    for fac in eligible_faculty:
                        # Check if faculty is unavailable during any of these periods
                        fac_unavail = False
                        for p in periods:
                            for unavail in fac.unavailable_slots:
                                if len(unavail) == 2 and unavail[0] == day and unavail[1] == p:
                                    fac_unavail = True
                                    break
                            if fac_unavail:
                                break
                        if fac_unavail:
                            continue

                        var_name = f"x_{s_idx}_{day}_{start_slot}_{room.id}_{fac.id}"
                        var = model.NewBoolVar(var_name)
                        key = (s_idx, day, start_slot, room.id, fac.id)
                        x_vars[key] = var
                        session_candidates[s_idx].append((key, var))

                        # Map to period occupancy
                        for p in periods:
                            faculty_period_vars[(fac.id, day, p)].append(var)
                            batch_period_vars[(batch.id, day, p)].append(var)
                            room_period_vars[(room.id, day, p)].append(var)

                        faculty_day_vars[(fac.id, day)].append((var, dur))
                        batch_day_vars[(batch.id, day)].append((var, start_slot, dur))
                        course_batch_day_vars[(course.id, batch.id, day)].append(var)

    # Constraint 1: Exactly one assignment per session
    for s_idx, session in enumerate(sessions):
        candidates = session_candidates[s_idx]
        if not candidates:
            # Cannot schedule this session due to complete constraint blockage
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
        model.AddExactlyOne([var for _, var in candidates])

    # Constraint 2: No faculty clashes (at most 1 class per faculty per period)
    for (fac_id, day, period), var_list in faculty_period_vars.items():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 3: No batch clashes (at most 1 class per student batch per period)
    for (batch_id, day, period), var_list in batch_period_vars.items():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 4: No room clashes (at most 1 class per room per period)
    for (room_id, day, period), var_list in room_period_vars.items():
        if len(var_list) > 1:
            model.Add(sum(var_list) <= 1)

    # Constraint 5: Faculty max daily hours
    for (fac_id, day), var_dur_list in faculty_day_vars.items():
        fac = faculty_by_id.get(fac_id)
        if fac and var_dur_list:
            model.Add(
                sum(var * dur for var, dur in var_dur_list) <= fac.max_daily_hours
            )

    # Constraint 6: Spread course lectures across days for a batch
    # (avoid cramming 3 lectures of the same course on the same day if weekly_hours <= days_count)
    for (course_id, batch_id, day), var_list in course_batch_day_vars.items():
        course = courses_by_id[course_id]
        if len(var_list) > 1:
            max_daily_sessions = 1 if course.weekly_hours <= days_count else 2
            model.Add(sum(var_list) <= max_daily_sessions)

    # 3. Soft Constraints & Multi-Objective Optimization
    objective_terms = []

    # Objective A: Faculty Preferred Slots (Reward bonus)
    pref_weight = int(weights.weight_faculty_preference * 10)
    for key, var in x_vars.items():
        s_idx, day, start_slot, room_id, fac_id = key
        session = sessions[s_idx]
        dur = session["duration"]
        fac = faculty_by_id.get(fac_id)
        if fac and fac.preferred_slots:
            is_preferred = False
            for p in range(start_slot, start_slot + dur):
                for pref in fac.preferred_slots:
                    if len(pref) == 2 and pref[0] == day and pref[1] == p:
                        is_preferred = True
                        break
                if is_preferred:
                    break
            if is_preferred:
                # Negative cost in minimization = reward
                objective_terms.append(-pref_weight * var)

    # Objective B: Preferred Room for Batch (Reward bonus)
    for key, var in x_vars.items():
        s_idx, day, start_slot, room_id, fac_id = key
        session = sessions[s_idx]
        batch = session["batch"]
        if batch.preferred_room_id and room_id == batch.preferred_room_id:
            objective_terms.append(-int(weights.weight_room_utilization * 5) * var)

    # Objective C: Student Workload Balance across Days
    # Penalize days with excessive or zero classes for batches
    ideal_daily_hours = 4  # approx ideal daily classes
    balance_weight = int(weights.weight_workload_balance * 8)
    for batch in dataset.batches:
        for day in range(days_count):
            vars_for_day = batch_day_vars.get((batch.id, day), [])
            if vars_for_day:
                day_total = model.NewIntVar(0, slots_per_day, f"day_hrs_{batch.id}_{day}")
                model.Add(day_total == sum(v * d for v, _, d in vars_for_day))
                # Penalize deviation from ideal daily hours
                dev_var = model.NewIntVar(0, slots_per_day, f"dev_{batch.id}_{day}")
                model.Add(dev_var >= day_total - ideal_daily_hours)
                model.Add(dev_var >= ideal_daily_hours - day_total)
                objective_terms.append(balance_weight * dev_var)

    # Objective D: Compact Student Schedule (Minimize idle gaps)
    # Penalize large spread between min slot and max slot relative to total classes
    student_idle_weight = int(weights.weight_idle_student * 12)
    for batch in dataset.batches:
        for day in range(days_count):
            vars_for_day = batch_day_vars.get((batch.id, day), [])
            if vars_for_day:
                min_slot_var = model.NewIntVar(0, slots_per_day, f"min_slot_{batch.id}_{day}")
                max_slot_var = model.NewIntVar(0, slots_per_day, f"max_slot_{batch.id}_{day}")
                has_any_class = model.NewBoolVar(f"has_class_{batch.id}_{day}")

                # If has_any_class == 0, spread is 0
                model.Add(sum(v for v, _, _ in vars_for_day) > 0).OnlyEnforceIf(has_any_class)
                model.Add(sum(v for v, _, _ in vars_for_day) == 0).OnlyEnforceIf(has_any_class.Not())

                for v, s_slot, dur in vars_for_day:
                    model.Add(min_slot_var <= s_slot).OnlyEnforceIf(v)
                    model.Add(max_slot_var >= s_slot + dur).OnlyEnforceIf(v)

                span_var = model.NewIntVar(0, slots_per_day, f"span_{batch.id}_{day}")
                model.Add(span_var >= max_slot_var - min_slot_var)
                # Idle time = span - total classes
                total_classes_var = model.NewIntVar(0, slots_per_day, f"tot_cls_{batch.id}_{day}")
                model.Add(total_classes_var == sum(v * d for v, _, d in vars_for_day))

                idle_var = model.NewIntVar(0, slots_per_day, f"idle_{batch.id}_{day}")
                model.Add(idle_var >= span_var - total_classes_var)
                objective_terms.append(student_idle_weight * idle_var)

    if objective_terms:
        model.Minimize(sum(objective_terms))

    # 4. Execute CP-SAT Solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    solver.parameters.num_workers = 4
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
                slot_time_str = (
                    f"{time_config.slot_times[start_slot].split(' - ')[0]} - "
                    f"{time_config.slot_times[start_slot + dur - 1].split(' - ')[1]}"
                    if start_slot + dur - 1 < len(time_config.slot_times)
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

        # Sort schedule chronologically
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
