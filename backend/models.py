"""
Data models and schemas for the Intelligent College Timetable Generator.
"""
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field


class RoomType(str, Enum):
    CLASSROOM = "CLASSROOM"
    LECTURE_HALL = "LECTURE_HALL"
    LAB_COMPUTER = "LAB_COMPUTER"
    LAB_ELECTRONICS = "LAB_ELECTRONICS"
    LAB_PHYSICS = "LAB_PHYSICS"
    LAB_MECHANICAL = "LAB_MECHANICAL"
    SEMINAR_HALL = "SEMINAR_HALL"


class CourseType(str, Enum):
    THEORY = "THEORY"
    LAB = "LAB"


class TimeConfig(BaseModel):
    days: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    slots_per_day: int = 8
    slot_times: List[str] = [
        "09:00 - 10:00",
        "10:00 - 11:00",
        "11:15 - 12:15",
        "12:15 - 13:15",
        "13:15 - 14:00 (Lunch)",
        "14:00 - 15:00",
        "15:00 - 16:00",
        "16:00 - 17:00"
    ]
    lunch_slot_idx: Optional[int] = 4  # 0-indexed, slot 4 is lunch
    break_slot_indices: List[int] = []


class Room(BaseModel):
    id: str
    name: str
    room_type: RoomType = RoomType.CLASSROOM
    capacity: int = 60
    building: str = "Main Block"
    floor: int = 1
    equipment: List[str] = []


class Faculty(BaseModel):
    id: str
    name: str
    department: str
    designation: str = "Assistant Professor"
    email: str = ""
    max_daily_hours: int = 4
    max_weekly_hours: int = 18
    # Unavailable slots: list of [day_idx, slot_idx]
    unavailable_slots: List[List[int]] = []
    # Preferred slots: list of [day_idx, slot_idx]
    preferred_slots: List[List[int]] = []
    qualified_courses: List[str] = []


class StudentBatch(BaseModel):
    id: str
    name: str
    department: str
    semester: int = 1
    size: int = 50
    preferred_room_id: Optional[str] = None


class Course(BaseModel):
    id: str
    code: str
    name: str
    department: str
    course_type: CourseType = CourseType.THEORY
    weekly_hours: int = 3
    credits: int = 3
    room_type_required: RoomType = RoomType.CLASSROOM
    consecutive_slots: int = 1  # 1 for standard theory, 2 or 3 for lab blocks
    faculty_ids: List[str] = []  # Qualified/assigned faculty IDs
    batch_ids: List[str] = []    # Target student batch IDs
    color: Optional[str] = "#3b82f6"


class TimetableSlot(BaseModel):
    id: str
    course_id: str
    course_code: str
    course_name: str
    course_type: CourseType
    batch_id: str
    batch_name: str
    faculty_id: str
    faculty_name: str
    room_id: str
    room_name: str
    day_idx: int
    day_name: str
    slot_idx: int
    slot_time: str
    duration: int = 1
    color: str = "#3b82f6"


class OptimizationWeights(BaseModel):
    weight_idle_student: float = 2.0
    weight_idle_faculty: float = 1.5
    weight_workload_balance: float = 1.2
    weight_room_utilization: float = 1.0
    weight_faculty_preference: float = 1.5


class TimetableDataset(BaseModel):
    name: str = "College Timetable"
    academic_term: str = "Fall 2026"
    time_config: TimeConfig = Field(default_factory=TimeConfig)
    rooms: List[Room] = []
    faculty: List[Faculty] = []
    batches: List[StudentBatch] = []
    courses: List[Course] = []
    weights: OptimizationWeights = Field(default_factory=OptimizationWeights)


class GenerationRequest(BaseModel):
    dataset: TimetableDataset
    solver_type: str = "cp_sat"  # "cp_sat" | "genetic" | "hybrid"
    max_time_seconds: int = 30
    ga_population_size: int = 100
    ga_generations: int = 250


class MetricDetail(BaseModel):
    value: float
    unit: str
    status: str  # "excellent" | "good" | "warning" | "danger"
    description: str


class ScheduleAnalytics(BaseModel):
    quality_score: float = 0.0  # 0 to 100
    hard_conflicts_count: int = 0
    total_slots_scheduled: int = 0
    batch_idle_hours_per_week: float = 0.0
    faculty_idle_hours_per_week: float = 0.0
    room_utilization_rate: float = 0.0  # percentage
    average_capacity_efficiency: float = 0.0  # percentage
    faculty_preference_satisfaction: float = 0.0  # percentage
    daily_workload_std_dev: float = 0.0
    metrics_breakdown: Dict[str, MetricDetail] = {}
    conflict_list: List[str] = []
    faculty_workloads: Dict[str, Dict[str, Any]] = {}
    room_occupancy: Dict[str, Dict[str, Any]] = {}
    batch_stats: Dict[str, Dict[str, Any]] = {}


class ScheduleResult(BaseModel):
    status: str  # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR"
    solver_type: str
    execution_time_sec: float
    hard_conflicts_count: int
    quality_score: float
    schedule: List[TimetableSlot] = []
    analytics: ScheduleAnalytics
    message: str = ""
