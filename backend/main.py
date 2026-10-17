"""
FastAPI application for the Intelligent College Timetable Generator.
Provides endpoints for generation, validation, analytics, export, and interactive slot modification.
"""
import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .models import (
    TimetableDataset,
    TimetableSlot,
    GenerationRequest,
    ScheduleResult,
    ScheduleAnalytics,
)
from .solvers.cp_sat_solver import solve_with_cp_sat
from .solvers.genetic_solver import solve_with_genetic_algorithm
from .analytics import validate_schedule, compute_analytics
from .presets import ALL_PRESETS, get_engineering_preset
from .exporters.excel_exporter import export_timetable_to_excel
from .exporters.pdf_exporter import export_timetable_to_pdf

app = FastAPI(
    title="Intelligent College Timetable Generator",
    description="Conflict-free timetable generation with OR-Tools CP-SAT & Genetic Algorithms",
    version="2.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExportRequest(BaseModel):
    dataset: TimetableDataset
    schedule: List[TimetableSlot]
    solver_type: str = "CP-SAT"
    execution_time_sec: float = 1.0


class SwapSlotRequest(BaseModel):
    dataset: TimetableDataset
    schedule: List[TimetableSlot]
    slot_id: str
    target_day_idx: int
    target_slot_idx: int
    target_room_id: Optional[str] = None


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "engine": "Intelligent College Timetable Generator",
        "version": "2.0.0",
    }


@app.get("/api/presets")
def get_presets():
    return [
        {
            "id": "engineering",
            "name": "Apex Institute of Technology",
            "subtitle": "Engineering & Computing (CS, AI, ECE - 4 Batches, 18 Courses, Labs & Lectures)",
            "batches_count": 4,
            "courses_count": 18,
            "rooms_count": 8,
            "faculty_count": 6,
        },
        {
            "id": "business",
            "name": "Horizon Graduate School of Business",
            "subtitle": "Management & Finance (MBA Cohorts, FinTech Lab, Amphitheaters)",
            "batches_count": 2,
            "courses_count": 4,
            "rooms_count": 4,
            "faculty_count": 3,
        },
    ]


@app.get("/api/preset/{preset_id}", response_model=TimetableDataset)
def get_preset_by_id(preset_id: str):
    if preset_id not in ALL_PRESETS:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return ALL_PRESETS[preset_id]()


@app.post("/api/generate", response_model=ScheduleResult)
def generate_timetable(req: GenerationRequest):
    try:
        if req.solver_type == "genetic":
            result = solve_with_genetic_algorithm(
                dataset=req.dataset,
                population_size=req.ga_population_size,
                generations=req.ga_generations,
                max_time_seconds=req.max_time_seconds,
                weights=req.dataset.weights,
            )
        else:
            # Default to CP-SAT
            result = solve_with_cp_sat(
                dataset=req.dataset,
                max_time_seconds=req.max_time_seconds,
                weights=req.dataset.weights,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solver error: {str(e)}")


@app.post("/api/validate", response_model=ScheduleAnalytics)
def validate_timetable(req: ExportRequest):
    analytics = compute_analytics(req.dataset, req.schedule)
    return analytics


@app.post("/api/swap-slot")
def swap_or_move_slot(req: SwapSlotRequest):
    """
    Simulates or executes moving a slot to a new day and period,
    and returns the updated schedule along with live conflict audit.
    """
    target_slot = None
    updated_schedule = []

    for s in req.schedule:
        if s.id == req.slot_id:
            target_slot = s
            # Create moved copy
            day_name = req.dataset.time_config.days[req.target_day_idx]
            slot_times = req.dataset.time_config.slot_times
            dur = s.duration
            end_p = req.target_slot_idx + dur - 1
            time_str = (
                f"{slot_times[req.target_slot_idx].split(' - ')[0]} - {slot_times[end_p].split(' - ')[1]}"
                if end_p < len(slot_times)
                else slot_times[req.target_slot_idx]
            )

            room_id = req.target_room_id or s.room_id
            room_name = s.room_name
            for r in req.dataset.rooms:
                if r.id == room_id:
                    room_name = r.name
                    break

            moved_slot = TimetableSlot(
                id=s.id,
                course_id=s.course_id,
                course_code=s.course_code,
                course_name=s.course_name,
                course_type=s.course_type,
                batch_id=s.batch_id,
                batch_name=s.batch_name,
                faculty_id=s.faculty_id,
                faculty_name=s.faculty_name,
                room_id=room_id,
                room_name=room_name,
                day_idx=req.target_day_idx,
                day_name=day_name,
                slot_idx=req.target_slot_idx,
                slot_time=time_str,
                duration=s.duration,
                color=s.color,
            )
            updated_schedule.append(moved_slot)
        else:
            updated_schedule.append(s)

    if not target_slot:
        raise HTTPException(status_code=404, detail=f"Slot '{req.slot_id}' not found.")

    analytics = compute_analytics(req.dataset, updated_schedule)
    return {
        "success": True,
        "updated_schedule": updated_schedule,
        "analytics": analytics,
        "has_conflicts": analytics.hard_conflicts_count > 0,
        "conflict_list": analytics.conflict_list,
    }


@app.post("/api/export/excel")
def export_excel(req: ExportRequest):
    analytics = compute_analytics(req.dataset, req.schedule)
    result = ScheduleResult(
        status="FEASIBLE" if analytics.hard_conflicts_count == 0 else "CONFLICTS_DETECTED",
        solver_type=req.solver_type,
        execution_time_sec=req.execution_time_sec,
        hard_conflicts_count=analytics.hard_conflicts_count,
        quality_score=analytics.quality_score,
        schedule=req.schedule,
        analytics=analytics,
    )
    xlsx_bytes = export_timetable_to_excel(req.dataset, result)
    filename = f"{req.dataset.name.replace(' ', '_')}_Timetable.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/pdf")
def export_pdf(req: ExportRequest):
    analytics = compute_analytics(req.dataset, req.schedule)
    result = ScheduleResult(
        status="FEASIBLE" if analytics.hard_conflicts_count == 0 else "CONFLICTS_DETECTED",
        solver_type=req.solver_type,
        execution_time_sec=req.execution_time_sec,
        hard_conflicts_count=analytics.hard_conflicts_count,
        quality_score=analytics.quality_score,
        schedule=req.schedule,
        analytics=analytics,
    )
    pdf_bytes = export_timetable_to_pdf(req.dataset, result)
    filename = f"{req.dataset.name.replace(' ', '_')}_Timetable.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Serve frontend static assets if dist exists
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
