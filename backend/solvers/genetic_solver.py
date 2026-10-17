"""
Genetic Algorithm (Evolutionary Metaheuristic) Solver for College Timetables.
Optimized with O(1) set-based evaluation, pre-filtered valid gene pools,
elitism, and domain-aware repair mutation.
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
    population_size: int = 60,
    generations: int = 150,
    max_time_seconds: int = 30,
    weights: OptimizationWeights = None,
) -> ScheduleResult:
    """
    High-performance Genetic Algorithm solver for college timetabling.
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

    # Pre-index faculty unavailabilities and preferences as fast O(1) sets
    fac_unavail_sets = {
        f.id: {tuple(u) for u in f.unavailable_slots if len(u) == 2}
        for f in dataset.faculty
    }
    fac_pref_sets = {
        f.id: {tuple(p) for p in f.preferred_slots if len(p) == 2}
        for f in dataset.faculty
    }
    fac_max_daily = {f.id: f.max_daily_hours for f in dataset.faculty}

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

    # 2. Pre-filter valid options per session (strictly pre-validated rooms & slots)
    session_options = []
    for s in sessions:
        course = s["course"]
        batch = s["batch"]
        dur = s["duration"]

        valid_slots = []
        for d in range(days_count):
            for slot in range(slots_per_day - dur + 1):
                periods = range(slot, slot + dur)
                if not any(p in break_slots for p in periods):
                    valid_slots.append((d, slot))

        if not valid_slots:
            valid_slots = [(0, 0)]

        # Pre-filter rooms matching room type and capacity
        pref_rooms = [
            r.id for r in dataset.rooms
            if r.room_type == course.room_type_required and r.capacity >= batch.size
        ]
        if not pref_rooms:
            pref_rooms = [r.id for r in dataset.rooms if r.room_type == course.room_type_required]
        if not pref_rooms:
            pref_rooms = [r.id for r in dataset.rooms]

        # Pre-filter qualified faculty
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

    num_sessions = len(sessions)

    # 3. Individual Generation (Semi-greedy constructive heuristic)
    def create_individual(smart: bool = True) -> List[Dict[str, Any]]:
        fac_busy = set()
        batch_busy = set()
        room_busy = set()

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
                shuffled_slots = list(opts["valid_slots"])
                random.shuffle(shuffled_slots)

                for d, sl in shuffled_slots:
                    periods = range(sl, sl + dur)
                    if any((b_id, d, p) in batch_busy for p in periods):
                        continue

                    avail_rooms = [
                        rid for rid in opts["pref_rooms"]
                        if not any((rid, d, p) in room_busy for p in periods)
                    ]
                    if not avail_rooms:
                        continue

                    avail_fac = []
                    for fid in opts["pref_faculty"]:
                        unavail = fac_unavail_sets.get(fid, set())
                        if not any((d, p) in unavail or (fid, d, p) in fac_busy for p in periods):
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

    # 4. Fast O(1) Fitness Evaluation
    weight_idle_s = int(weights.weight_idle_student * 12)
    weight_idle_f = int(weights.weight_idle_faculty * 8)
    weight_pref = int(weights.weight_faculty_preference * 15)

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

        for i in range(num_sessions):
            gene = individual[i]
            dur = sessions[i]["duration"]
            b_id = sessions[i]["batch"].id
            d = gene["day"]
            sl = gene["slot"]
            r_id = gene["room_id"]
            f_id = gene["faculty_id"]

            # Fast faculty unavailable check via O(1) set
            fac_unavail = fac_unavail_sets.get(f_id, set())
            fac_prefs = fac_pref_sets.get(f_id, set())

            for p in range(sl, sl + dur):
                if (d, p) in fac_unavail:
                    hard_penalties += 2500
                    hard_conflicts += 1

                if fac_prefs and (d, p) in fac_prefs:
                    pref_hits += 1

                f_key = (f_id, d, p)
                b_key = (b_id, d, p)
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
            batch_day_slots[b_id][d].extend(range(sl, sl + dur))
            fac_day_slots[f_id][d].extend(range(sl, sl + dur))

        # Max daily load for faculty
        for f_id, d_map in fac_daily_load.items():
            max_daily = fac_max_daily.get(f_id, 4)
            for d, load in d_map.items():
                if load > max_daily:
                    overflow = load - max_daily
                    hard_penalties += overflow * 1500
                    hard_conflicts += overflow

        # Student idle gaps
        soft_penalties = 0
        for b_id, day_map in batch_day_slots.items():
            for d, sl_list in day_map.items():
                if len(sl_list) >= 2:
                    sorted_sl = sorted(sl_list)
                    min_p, max_p = sorted_sl[0], sorted_sl[-1]
                    for p in range(min_p, max_p + 1):
                        if p not in sorted_sl and p != lunch_idx:
                            soft_penalties += weight_idle_s

        # Faculty idle gaps
        for f_id, day_map in fac_day_slots.items():
            for d, sl_list in day_map.items():
                if len(sl_list) >= 2:
                    sorted_sl = sorted(sl_list)
                    min_p, max_p = sorted_sl[0], sorted_sl[-1]
                    for p in range(min_p, max_p + 1):
                        if p not in sorted_sl and p != lunch_idx:
                            soft_penalties += weight_idle_f

        fitness = 50000.0 - hard_penalties - soft_penalties + (pref_hits * weight_pref)
        return fitness, hard_conflicts

    # 5. Fast Domain-Aware Repair Operator
    def repair_individual(ind: List[Dict[str, Any]]):
        occupied_batch = set()
        occupied_fac = set()
        occupied_room = set()

        for idx in range(num_sessions):
            gene = ind[idx]
            dur = sessions[idx]["duration"]
            b_id = sessions[idx]["batch"].id
            d = gene["day"]
            sl = gene["slot"]
            r_id = gene["room_id"]
            f_id = gene["faculty_id"]

            has_clash = any(
                (b_id, d, p) in occupied_batch or (f_id, d, p) in occupied_fac or (r_id, d, p) in occupied_room
                for p in range(sl, sl + dur)
            )

            if has_clash:
                opts = session_options[idx]
                shuffled_slots = list(opts["valid_slots"])
                random.shuffle(shuffled_slots)

                for alt_d, alt_sl in shuffled_slots:
                    periods = range(alt_sl, alt_sl + dur)
                    if any((b_id, alt_d, p) in occupied_batch for p in periods):
                        continue

                    avail_rooms = [
                        rid for rid in opts["pref_rooms"]
                        if not any((rid, alt_d, p) in occupied_room for p in periods)
                    ]
                    if not avail_rooms:
                        continue

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
                    break

            d, sl, r_id, f_id = gene["day"], gene["slot"], gene["room_id"], gene["faculty_id"]
            for p in range(sl, sl + dur):
                occupied_batch.add((b_id, d, p))
                occupied_fac.add((f_id, d, p))
                occupied_room.add((r_id, d, p))

    # 6. Initialize Population
    population = [
        create_individual(smart=(i < int(population_size * 0.75)))
        for i in range(population_size)
    ]

    best_individual = None
    best_fitness = -float("inf")
    best_hard_conflicts = 999999

    crossover_rate = 0.85
    mutation_rate = 0.25
    elite_count = max(2, int(population_size * 0.10))

    # 7. Evolution Loop
    for gen in range(generations):
        if time.time() - start_time > max_time_seconds:
            break

        evaluated = []
        for ind in population:
            fit, h_conf = evaluate(ind)
            evaluated.append((fit, h_conf, ind))
            if fit > best_fitness:
                best_fitness = fit
                best_hard_conflicts = h_conf
                best_individual = [dict(g) for g in ind]

        if best_hard_conflicts == 0 and gen > 50:
            break

        evaluated.sort(key=lambda x: x[0], reverse=True)
        next_gen = [evaluated[i][2] for i in range(elite_count)]

        def tournament_select():
            contenders = random.sample(evaluated, 4)
            contenders.sort(key=lambda x: x[0], reverse=True)
            return contenders[0][2]

        while len(next_gen) < population_size:
            p1 = tournament_select()
            p2 = tournament_select()

            child1 = [dict(g) for g in p1]
            child2 = [dict(g) for g in p2]
            if random.random() < crossover_rate:
                cx_point = random.randint(1, num_sessions - 1)
                child1 = [dict(g) for g in p1[:cx_point]] + [dict(g) for g in p2[cx_point:]]
                child2 = [dict(g) for g in p2[:cx_point]] + [dict(g) for g in p1[cx_point:]]

            for child in (child1, child2):
                if random.random() < mutation_rate:
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

                if random.random() < 0.35:
                    repair_individual(child)

                if len(next_gen) < population_size:
                    next_gen.append(child)

        population = next_gen

    exec_time = time.time() - start_time

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
        end_slot = sl + dur - 1
        slot_time_str = (
            f"{time_config.slot_times[sl].split(' - ')[0]} - "
            f"{time_config.slot_times[end_slot].split(' - ')[1]}"
            if end_slot < len(time_config.slot_times)
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
