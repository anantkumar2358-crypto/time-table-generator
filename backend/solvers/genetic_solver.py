"""
Genetic Algorithm (Evolutionary Metaheuristic) Solver for College Timetables.
Features domain-aware repair mutation, elitism, multi-objective fitness evaluation,
and adaptive search operators.
"""
import time
import random
from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict

from ..models import (
    TimetableDataset,
    TimetableSlot,
    ScheduleResult,
    OptimizationWeights,
    CourseType,
)
from ..analytics import compute_analytics


def solve_with_genetic_algorithm(
    dataset: TimetableDataset,
    population_size: int = 80,
    generations: int = 200,
    max_time_seconds: int = 30,
    weights: OptimizationWeights = None,
) -> ScheduleResult:
    """
    Solves the college timetable problem using an advanced Genetic Algorithm.
    """
    start_time = time.time()
    if weights is None:
        weights = dataset.weights

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

    # 1. Decompose courses into sessions
    sessions = []
    session_counter = 0

    for course in dataset.courses:
        block_dur = course.consecutive_slots if course.consecutive_slots > 0 else 1
        rem_hours = course.weekly_hours

        for b_id in course.batch_ids:
            batch = batches_by_id.get(b_id)
            if not batch:
                continue

            hrs = rem_hours
            while hrs > 0:
                cur_dur = min(hrs, block_dur)
                session_counter += 1
                sessions.append({
                    "id": session_counter,
                    "course": course,
                    "batch": batch,
                    "duration": cur_dur,
                })
                hrs -= cur_dur

    if not sessions:
        exec_time = time.time() - start_time
        return ScheduleResult(
            status="FEASIBLE",
            solver_type="Genetic Algorithm",
            execution_time_sec=round(exec_time, 2),
            hard_conflicts_count=0,
            quality_score=100.0,
            schedule=[],
            analytics=compute_analytics(dataset, []),
            message="No sessions to schedule."
        )

    # 2. Determine valid options for each session
    session_options = []
    for s in sessions:
        course = s["course"]
        batch = s["batch"]
        dur = s["duration"]

        # Valid (day, start_slot)
        valid_slots = []
        for d in range(days_count):
            for slot in range(slots_per_day - dur + 1):
                periods = range(slot, slot + dur)
                if not any(p in break_slots for p in periods):
                    valid_slots.append((d, slot))

        if not valid_slots:
            valid_slots = [(0, 0)]

        # Valid rooms (preferred: matching type and capacity)
        pref_rooms = [
            r.id for r in dataset.rooms
            if r.room_type == course.room_type_required and r.capacity >= batch.size
        ]
        if not pref_rooms:
            pref_rooms = [r.id for r in dataset.rooms if r.room_type == course.room_type_required]
        if not pref_rooms:
            pref_rooms = [r.id for r in dataset.rooms]

        # Valid faculty
        if course.faculty_ids:
            pref_faculty = [fid for fid in course.faculty_ids if fid in faculty_by_id]
        else:
            pref_faculty = [f.id for f in dataset.faculty if f.department == course.department]
        if not pref_faculty:
            pref_faculty = [f.id for f in dataset.faculty]

        session_options.append({
            "valid_slots": valid_slots,
            "pref_rooms": pref_rooms,
            "pref_faculty": pref_faculty,
        })

    # 3. Chromosome representation
    # An individual is a list of genes: [{'day': d, 'slot': s, 'room_id': r, 'faculty_id': f}, ...]
    num_sessions = len(sessions)

    def create_individual(smart: bool = True) -> List[Dict[str, Any]]:
        ind = []
        # Track occupied for smart heuristic placement
        fac_busy = set()
        batch_busy = set()
        room_busy = set()

        # Sort sessions by difficulty (longer duration / labs first)
        order = list(range(num_sessions))
        if smart:
            order.sort(key=lambda idx: -sessions[idx]["duration"])

        genes = [None] * num_sessions
        for idx in order:
            opts = session_options[idx]
            dur = sessions[idx]["duration"]
            b_id = sessions[idx]["batch"].id

            chosen_slot = None
            chosen_room = None
            chosen_fac = None

            if smart:
                # Try finding a slot that doesn't clash with already placed sessions
                shuffled_slots = list(opts["valid_slots"])
                random.shuffle(shuffled_slots)

                for d, sl in shuffled_slots:
                    periods = range(sl, sl + dur)
                    # Check if batch is busy
                    if any((b_id, d, p) in batch_busy for p in periods):
                        continue

                    # Find a free room
                    avail_rooms = [
                        rid for rid in opts["pref_rooms"]
                        if not any((rid, d, p) in room_busy for p in periods)
                    ]
                    if not avail_rooms:
                        continue

                    # Find a free faculty
                    avail_fac = []
                    for fid in opts["pref_faculty"]:
                        fac = faculty_by_id[fid]
                        # Check unavailable slots
                        unavail = False
                        for p in periods:
                            if [d, p] in fac.unavailable_slots:
                                unavail = True
                                break
                        if not unavail and not any((fid, d, p) in fac_busy for p in periods):
                            avail_fac.append(fid)

                    if avail_rooms and avail_fac:
                        chosen_slot = (d, sl)
                        chosen_room = random.choice(avail_rooms)
                        chosen_fac = random.choice(avail_fac)
                        break

            if chosen_slot is None:
                chosen_slot = random.choice(opts["valid_slots"])
                chosen_room = random.choice(opts["pref_rooms"])
                chosen_fac = random.choice(opts["pref_faculty"])

            d, sl = chosen_slot
            for p in range(sl, sl + dur):
                batch_busy.add((b_id, d, p))
                room_busy.add((chosen_room, d, p))
                fac_busy.add((chosen_fac, d, p))

            genes[idx] = {
                "day": d,
                "slot": sl,
                "room_id": chosen_room,
                "faculty_id": chosen_fac,
            }
        return genes

    # 4. Fitness Evaluation
    def evaluate(individual: List[Dict[str, Any]]) -> Tuple[float, int]:
        hard_penalties = 0
        hard_conflicts = 0

        faculty_occ = defaultdict(int)
        batch_occ = defaultdict(int)
        room_occ = defaultdict(int)
        fac_daily_load = defaultdict(lambda: defaultdict(int))
        batch_day_slots = defaultdict(lambda: defaultdict(list))
        fac_day_slots = defaultdict(lambda: defaultdict(list))

        pref_hits = 0

        for i, gene in enumerate(individual):
            s = sessions[i]
            dur = s["duration"]
            course = s["course"]
            batch = s["batch"]
            d = gene["day"]
            sl = gene["slot"]
            r_id = gene["room_id"]
            f_id = gene["faculty_id"]

            room = rooms_by_id.get(r_id)
            fac = faculty_by_id.get(f_id)

            # Capacity check
            if room and room.capacity < batch.size:
                hard_penalties += 2000
                hard_conflicts += 1

            # Room type check
            if room and room.room_type != course.room_type_required:
                hard_penalties += 3000
                hard_conflicts += 1

            # Faculty unavailable check
            if fac:
                for p in range(sl, sl + dur):
                    for unavail in fac.unavailable_slots:
                        if len(unavail) == 2 and unavail[0] == d and unavail[1] == p:
                            hard_penalties += 2500
                            hard_conflicts += 1

            # Lunch overlap
            if lunch_idx is not None:
                for p in range(sl, sl + dur):
                    if p == lunch_idx:
                        hard_penalties += 3000
                        hard_conflicts += 1

            # Record period usage
            for p in range(sl, sl + dur):
                f_key = (f_id, d, p)
                b_key = (batch.id, d, p)
                r_key = (r_id, d, p)

                faculty_occ[f_key] += 1
                if faculty_occ[f_key] > 1:
                    hard_penalties += 2000
                    hard_conflicts += 1

                batch_occ[b_key] += 1
                if batch_occ[b_key] > 1:
                    hard_penalties += 2000
                    hard_conflicts += 1

                room_occ[r_key] += 1
                if room_occ[r_key] > 1:
                    hard_penalties += 2000
                    hard_conflicts += 1

            fac_daily_load[f_id][d] += dur
            batch_day_slots[batch.id][d].extend(range(sl, sl + dur))
            fac_day_slots[f_id][d].extend(range(sl, sl + dur))

            # Preferred slot bonus
            if fac and fac.preferred_slots:
                for p in range(sl, sl + dur):
                    for pref in fac.preferred_slots:
                        if len(pref) == 2 and pref[0] == d and pref[1] == p:
                            pref_hits += 1

        # Max daily load for faculty
        for f_id, d_map in fac_daily_load.items():
            fac = faculty_by_id.get(f_id)
            if fac:
                for d, load in d_map.items():
                    if load > fac.max_daily_hours:
                        overflow = load - fac.max_daily_hours
                        hard_penalties += overflow * 1500
                        hard_conflicts += overflow

        # Soft penalties: student idle gaps
        soft_penalties = 0
        for b_id, day_map in batch_day_slots.items():
            for d, sl_list in day_map.items():
                if len(sl_list) >= 2:
                    sorted_sl = sorted(sl_list)
                    min_p, max_p = sorted_sl[0], sorted_sl[-1]
                    for p in range(min_p, max_p + 1):
                        if p not in sorted_sl and p != lunch_idx:
                            soft_penalties += int(weights.weight_idle_student * 15)

        # Soft penalties: faculty idle gaps
        for f_id, day_map in fac_day_slots.items():
            for d, sl_list in day_map.items():
                if len(sl_list) >= 2:
                    sorted_sl = sorted(sl_list)
                    min_p, max_p = sorted_sl[0], sorted_sl[-1]
                    for p in range(min_p, max_p + 1):
                        if p not in sorted_sl and p != lunch_idx:
                            soft_penalties += int(weights.weight_idle_faculty * 10)

        # Base fitness: 50,000 pts
        fitness = 50000.0 - hard_penalties - soft_penalties + (pref_hits * int(weights.weight_faculty_preference * 20))
        return fitness, hard_conflicts

    # 5. Domain-Aware Repair Operator
    def repair_individual(ind: List[Dict[str, Any]]):
        """
        Pinpoints clashing sessions and re-assigns them to non-conflicting slots.
        """
        occupied_batch = set()
        occupied_fac = set()
        occupied_room = set()

        for idx, gene in enumerate(ind):
            s = sessions[idx]
            dur = s["duration"]
            b_id = s["batch"].id
            d = gene["day"]
            sl = gene["slot"]
            r_id = gene["room_id"]
            f_id = gene["faculty_id"]

            has_clash = False
            for p in range(sl, sl + dur):
                if (b_id, d, p) in occupied_batch or (f_id, d, p) in occupied_fac or (r_id, d, p) in occupied_room:
                    has_clash = True
                    break

            if has_clash:
                # Attempt to find alternative clash-free placement
                opts = session_options[idx]
                found = False
                shuffled_slots = list(opts["valid_slots"])
                random.shuffle(shuffled_slots)

                for alt_d, alt_sl in shuffled_slots:
                    periods = range(alt_sl, alt_sl + dur)
                    if any((b_id, alt_d, p) in occupied_batch for p in periods):
                        continue

                    # Free room
                    avail_rooms = [
                        rid for rid in opts["pref_rooms"]
                        if not any((rid, alt_d, p) in occupied_room for p in periods)
                    ]
                    if not avail_rooms:
                        continue

                    # Free faculty
                    avail_fac = [
                        fid for fid in opts["pref_faculty"]
                        if not any((fid, alt_d, p) in occupied_fac for p in periods)
                    ]
                    if not avail_fac:
                        continue

                    gene["day"] = alt_d
                    gene["slot"] = alt_sl
                    gene["room_id"] = random.choice(avail_rooms)
                    gene["faculty_id"] = random.choice(avail_fac)
                    found = True
                    break

                if not found:
                    # Random fallback
                    gene["slot"] = random.choice(opts["valid_slots"])[1]

            # Mark as occupied
            d, sl, r_id, f_id = gene["day"], gene["slot"], gene["room_id"], gene["faculty_id"]
            for p in range(sl, sl + dur):
                occupied_batch.add((b_id, d, p))
                occupied_fac.add((f_id, d, p))
                occupied_room.add((r_id, d, p))

    # 6. Initialize Population
    population = []
    # 70% smart heuristic, 30% random
    for i in range(population_size):
        ind = create_individual(smart=(i < int(population_size * 0.7)))
        population.append(ind)

    best_individual = None
    best_fitness = -float("inf")
    best_hard_conflicts = 999999

    # 7. Evolution Loop
    crossover_rate = 0.85
    mutation_rate = 0.25
    elite_count = max(2, int(population_size * 0.10))

    for gen in range(generations):
        # Time budget check
        if time.time() - start_time > max_time_seconds:
            break

        # Evaluate all
        evaluated = []
        for ind in population:
            fit, h_conf = evaluate(ind)
            evaluated.append((fit, h_conf, ind))
            if fit > best_fitness:
                best_fitness = fit
                best_hard_conflicts = h_conf
                best_individual = [dict(g) for g in ind]

        # Early exit if 0 hard conflicts and fitness is high
        if best_hard_conflicts == 0 and gen > 60:
            break

        # Sort by fitness descending
        evaluated.sort(key=lambda x: x[0], reverse=True)

        # Elites
        next_gen = [evaluated[i][2] for i in range(elite_count)]

        # Tournament selection
        def tournament_select():
            contenders = random.sample(evaluated, 4)
            contenders.sort(key=lambda x: x[0], reverse=True)
            return contenders[0][2]

        while len(next_gen) < population_size:
            p1 = tournament_select()
            p2 = tournament_select()

            # Crossover
            child1 = [dict(g) for g in p1]
            child2 = [dict(g) for g in p2]
            if random.random() < crossover_rate:
                # Multi-point crossover
                cx_point = random.randint(1, num_sessions - 1)
                child1 = [dict(g) for g in p1[:cx_point]] + [dict(g) for g in p2[cx_point:]]
                child2 = [dict(g) for g in p2[:cx_point]] + [dict(g) for g in p1[cx_point:]]

            # Mutation
            for child in (child1, child2):
                if random.random() < mutation_rate:
                    # Pick random gene to mutate
                    mut_idx = random.randint(0, num_sessions - 1)
                    opts = session_options[mut_idx]
                    mut_type = random.random()
                    if mut_type < 0.5:
                        d, sl = random.choice(opts["valid_slots"])
                        child[mut_idx]["day"] = d
                        child[mut_idx]["slot"] = sl
                    elif mut_type < 0.75:
                        child[mut_idx]["room_id"] = random.choice(opts["pref_rooms"])
                    else:
                        child[mut_idx]["faculty_id"] = random.choice(opts["pref_faculty"])

                # Apply repair operator
                if random.random() < 0.35:
                    repair_individual(child)

                if len(next_gen) < population_size:
                    next_gen.append(child)

        population = next_gen

    exec_time = time.time() - start_time

    # 8. Convert Best Individual to ScheduleResult
    if best_individual is None:
        best_individual = population[0]

    schedule = []
    slot_id = 0
    for idx, gene in enumerate(best_individual):
        s = sessions[idx]
        course = s["course"]
        batch = s["batch"]
        dur = s["duration"]
        d = gene["day"]
        sl = gene["slot"]
        r_id = gene["room_id"]
        f_id = gene["faculty_id"]

        room = rooms_by_id[r_id]
        fac = faculty_by_id[f_id]

        slot_id += 1
        slot_time_str = (
            f"{time_config.slot_times[sl].split(' - ')[0]} - "
            f"{time_config.slot_times[sl + dur - 1].split(' - ')[1]}"
            if sl + dur - 1 < len(time_config.slot_times)
            else time_config.slot_times[sl]
        )

        schedule.append(
            TimetableSlot(
                id=f"ga_slot_{slot_id}",
                course_id=course.id,
                course_code=course.code,
                course_name=course.name,
                course_type=course.course_type,
                batch_id=batch.id,
                batch_name=batch.name,
                faculty_id=fac.id,
                faculty_name=fac.name,
                room_id=room.id,
                room_name=room.name,
                day_idx=d,
                day_name=days[d],
                slot_idx=sl,
                slot_time=slot_time_str,
                duration=dur,
                color=course.color or "#3b82f6",
            )
        )

    schedule.sort(key=lambda s: (s.day_idx, s.slot_idx, s.batch_name))
    analytics = compute_analytics(dataset, schedule)

    status_str = "OPTIMAL" if analytics.hard_conflicts_count == 0 else "FEASIBLE"
    msg = (
        f"Genetic Algorithm evolved {population_size} candidates across generations in {round(exec_time, 2)}s. "
        f"Hard clashes: {analytics.hard_conflicts_count}, Quality score: {analytics.quality_score}/100."
    )

    return ScheduleResult(
        status=status_str,
        solver_type="Genetic Algorithm",
        execution_time_sec=round(exec_time, 2),
        hard_conflicts_count=analytics.hard_conflicts_count,
        quality_score=analytics.quality_score,
        schedule=schedule,
        analytics=analytics,
        message=msg,
    )
