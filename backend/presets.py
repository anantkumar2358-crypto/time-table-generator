"""
Rich, realistic preset datasets for college timetabling across various academic domains.
"""
from typing import Dict
from .models import (
    TimetableDataset,
    TimeConfig,
    Room,
    RoomType,
    Faculty,
    StudentBatch,
    Course,
    CourseType,
    OptimizationWeights,
)


def get_engineering_preset() -> TimetableDataset:
    time_config = TimeConfig(
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        slots_per_day=8,
        slot_times=[
            "09:00 - 10:00",
            "10:00 - 11:00",
            "11:15 - 12:15",
            "12:15 - 13:15 (Lunch)",
            "13:15 - 14:15",
            "14:15 - 15:15",
            "15:15 - 16:15",
            "16:15 - 17:15",
        ],
        lunch_slot_idx=3,
        break_slot_indices=[],
    )

    rooms = [
        Room(id="r_lh101", name="LH-101 (Turing Theater)", room_type=RoomType.LECTURE_HALL, capacity=75, building="Main Academic", floor=1, equipment=["Projector", "Surround Sound", "Smart Podium"]),
        Room(id="r_lh102", name="LH-102 (Von Neumann Hall)", room_type=RoomType.LECTURE_HALL, capacity=75, building="Main Academic", floor=1, equipment=["Dual Projector", "Smart Board"]),
        Room(id="r_cr201", name="CR-201 (Ramanujan Room)", room_type=RoomType.CLASSROOM, capacity=60, building="East Wing", floor=2, equipment=["Whiteboard", "Projector"]),
        Room(id="r_cr202", name="CR-202 (Shannon Room)", room_type=RoomType.CLASSROOM, capacity=60, building="East Wing", floor=2, equipment=["Whiteboard", "Projector"]),
        Room(id="r_lab_cs1", name="CS Lab 1 (Algorithms)", room_type=RoomType.LAB_COMPUTER, capacity=65, building="Computing Complex", floor=1, equipment=["65 Workstations", "Gigabit LAN", "Linux Servers"]),
        Room(id="r_lab_cs2", name="CS Lab 2 (AI & Cloud)", room_type=RoomType.LAB_COMPUTER, capacity=60, building="Computing Complex", floor=2, equipment=["60 GPU Workstations", "Cloud Cluster Access"]),
        Room(id="r_lab_ece", name="ECE Circuits Lab", room_type=RoomType.LAB_ELECTRONICS, capacity=50, building="Technology Block", floor=1, equipment=["Digital Oscilloscopes", "Signal Generators", "FPGA Kits"]),
        Room(id="r_sem_hall", name="Seminar Auditorium", room_type=RoomType.SEMINAR_HALL, capacity=120, building="Main Academic", floor=3, equipment=["Conference PA System", "Stage Display"]),
    ]

    faculty = [
        Faculty(
            id="fac_sharma",
            name="Dr. Rajesh Sharma",
            department="Computer Science",
            designation="Professor & HOD",
            email="r.sharma@apex.edu",
            max_daily_hours=3,
            max_weekly_hours=14,
            # Blackout during HOD executive meeting: Monday period 0 (9-10 AM)
            unavailable_slots=[[0, 0]],
            preferred_slots=[[0, 1], [1, 1], [2, 1], [3, 1], [4, 1]],  # Prefers morning slot 1
            qualified_courses=["cs301", "cs305"],
        ),
        Faculty(
            id="fac_ananya",
            name="Dr. Ananya Roy",
            department="Computer Science",
            designation="Associate Professor",
            email="a.roy@apex.edu",
            max_daily_hours=4,
            max_weekly_hours=16,
            unavailable_slots=[[4, 6], [4, 7]],  # Friday afternoon conference
            preferred_slots=[[1, 2], [2, 2], [3, 2]],
            qualified_courses=["cs302", "cs306"],
        ),
        Faculty(
            id="fac_vikram",
            name="Prof. Vikram Patel",
            department="Computer Science",
            designation="Assistant Professor",
            email="v.patel@apex.edu",
            max_daily_hours=4,
            max_weekly_hours=18,
            unavailable_slots=[],
            preferred_slots=[[0, 2], [1, 1], [3, 0]],
            qualified_courses=["cs303", "cs307"],
        ),
        Faculty(
            id="fac_priya",
            name="Dr. Priya Nambiar",
            department="Artificial Intelligence",
            designation="Associate Professor",
            email="p.nambiar@apex.edu",
            max_daily_hours=4,
            max_weekly_hours=16,
            unavailable_slots=[[2, 5], [2, 6]],  # Wednesday afternoon lab research
            preferred_slots=[[0, 1], [2, 0], [4, 2]],
            qualified_courses=["ai301", "ai302"],
        ),
        Faculty(
            id="fac_kulkarni",
            name="Prof. Suresh Kulkarni",
            department="Electronics",
            designation="Associate Professor",
            email="s.kulkarni@apex.edu",
            max_daily_hours=4,
            max_weekly_hours=16,
            unavailable_slots=[[1, 0]],  # Tuesday morning research
            preferred_slots=[[1, 1], [2, 1], [3, 1]],
            qualified_courses=["ec301", "ec302"],
        ),
        Faculty(
            id="fac_math",
            name="Dr. K. S. Raman",
            department="Mathematics",
            designation="Professor",
            email="ks.raman@apex.edu",
            max_daily_hours=3,
            max_weekly_hours=14,
            unavailable_slots=[[4, 5], [4, 6], [4, 7]],  # Friday evening seminar
            preferred_slots=[[0, 0], [1, 0], [2, 0], [3, 0]],  # Loves early 9 AM classes
            qualified_courses=["ma301"],
        ),
    ]

    batches = [
        StudentBatch(id="batch_cs_a", name="CSE 2nd Year - Sec A", department="Computer Science", semester=3, size=55, preferred_room_id="r_lh101"),
        StudentBatch(id="batch_cs_b", name="CSE 2nd Year - Sec B", department="Computer Science", semester=3, size=52, preferred_room_id="r_lh102"),
        StudentBatch(id="batch_ai", name="AI & Data Science - 2nd Year", department="Artificial Intelligence", semester=3, size=48, preferred_room_id="r_cr201"),
        StudentBatch(id="batch_ece", name="ECE 3rd Year - Sec A", department="Electronics", semester=5, size=42, preferred_room_id="r_cr202"),
    ]

    courses = [
        # Batch CS-A Courses
        Course(
            id="cs301_a",
            code="CS301",
            name="Data Structures & Algorithms",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_sharma"],
            batch_ids=["batch_cs_a"],
            color="#3b82f6",  # Blue
        ),
        Course(
            id="cs301_lab_a",
            code="CS301L",
            name="Data Structures Lab",
            department="Computer Science",
            course_type=CourseType.LAB,
            weekly_hours=2,
            credits=1,
            room_type_required=RoomType.LAB_COMPUTER,
            consecutive_slots=2,  # 2-hour lab block
            faculty_ids=["fac_sharma"],
            batch_ids=["batch_cs_a"],
            color="#1d4ed8",  # Dark Blue
        ),
        Course(
            id="cs302_a",
            code="CS302",
            name="Database Management Systems",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_ananya"],
            batch_ids=["batch_cs_a"],
            color="#10b981",  # Green
        ),
        Course(
            id="cs302_lab_a",
            code="CS302L",
            name="DBMS Lab",
            department="Computer Science",
            course_type=CourseType.LAB,
            weekly_hours=2,
            credits=1,
            room_type_required=RoomType.LAB_COMPUTER,
            consecutive_slots=2,  # 2-hour lab block
            faculty_ids=["fac_ananya"],
            batch_ids=["batch_cs_a"],
            color="#047857",  # Dark Green
        ),
        Course(
            id="cs303_a",
            code="CS303",
            name="Operating Systems",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_vikram"],
            batch_ids=["batch_cs_a"],
            color="#8b5cf6",  # Purple
        ),
        Course(
            id="ma301_a",
            code="MA301",
            name="Discrete Mathematics",
            department="Mathematics",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_math"],
            batch_ids=["batch_cs_a"],
            color="#f59e0b",  # Amber
        ),

        # Batch CS-B Courses
        Course(
            id="cs301_b",
            code="CS301",
            name="Data Structures & Algorithms",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_sharma"],
            batch_ids=["batch_cs_b"],
            color="#3b82f6",
        ),
        Course(
            id="cs301_lab_b",
            code="CS301L",
            name="Data Structures Lab",
            department="Computer Science",
            course_type=CourseType.LAB,
            weekly_hours=2,
            credits=1,
            room_type_required=RoomType.LAB_COMPUTER,
            consecutive_slots=2,
            faculty_ids=["fac_sharma"],
            batch_ids=["batch_cs_b"],
            color="#1d4ed8",
        ),
        Course(
            id="cs302_b",
            code="CS302",
            name="Database Management Systems",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_ananya"],
            batch_ids=["batch_cs_b"],
            color="#10b981",
        ),
        Course(
            id="cs303_b",
            code="CS303",
            name="Operating Systems",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_vikram"],
            batch_ids=["batch_cs_b"],
            color="#8b5cf6",
        ),
        Course(
            id="ma301_b",
            code="MA301",
            name="Discrete Mathematics",
            department="Mathematics",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.LECTURE_HALL,
            consecutive_slots=1,
            faculty_ids=["fac_math"],
            batch_ids=["batch_cs_b"],
            color="#f59e0b",
        ),

        # Batch AI Courses
        Course(
            id="ai301",
            code="AI301",
            name="Machine Learning Foundations",
            department="Artificial Intelligence",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.CLASSROOM,
            consecutive_slots=1,
            faculty_ids=["fac_priya"],
            batch_ids=["batch_ai"],
            color="#ec4899",  # Pink
        ),
        Course(
            id="ai301_lab",
            code="AI301L",
            name="Machine Learning Lab",
            department="Artificial Intelligence",
            course_type=CourseType.LAB,
            weekly_hours=2,
            credits=1,
            room_type_required=RoomType.LAB_COMPUTER,
            consecutive_slots=2,
            faculty_ids=["fac_priya"],
            batch_ids=["batch_ai"],
            color="#be185d",  # Deep Pink
        ),
        Course(
            id="ai302",
            code="AI302",
            name="Probability & Statistics for AI",
            department="Artificial Intelligence",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.CLASSROOM,
            consecutive_slots=1,
            faculty_ids=["fac_math"],
            batch_ids=["batch_ai"],
            color="#06b6d4",  # Cyan
        ),
        Course(
            id="ai303",
            code="CS303",
            name="Operating Systems",
            department="Computer Science",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.CLASSROOM,
            consecutive_slots=1,
            faculty_ids=["fac_vikram"],
            batch_ids=["batch_ai"],
            color="#8b5cf6",
        ),

        # Batch ECE Courses
        Course(
            id="ec301",
            code="EC301",
            name="Digital Signal Processing",
            department="Electronics",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.CLASSROOM,
            consecutive_slots=1,
            faculty_ids=["fac_kulkarni"],
            batch_ids=["batch_ece"],
            color="#e11d48",  # Rose
        ),
        Course(
            id="ec301_lab",
            code="EC301L",
            name="DSP & Circuits Lab",
            department="Electronics",
            course_type=CourseType.LAB,
            weekly_hours=2,
            credits=1,
            room_type_required=RoomType.LAB_ELECTRONICS,
            consecutive_slots=2,
            faculty_ids=["fac_kulkarni"],
            batch_ids=["batch_ece"],
            color="#9f1239",
        ),
        Course(
            id="ec302",
            code="EC302",
            name="Microprocessors & Embedded Systems",
            department="Electronics",
            course_type=CourseType.THEORY,
            weekly_hours=3,
            credits=3,
            room_type_required=RoomType.CLASSROOM,
            consecutive_slots=1,
            faculty_ids=["fac_kulkarni"],
            batch_ids=["batch_ece"],
            color="#d97706",
        ),
    ]

    return TimetableDataset(
        name="Apex Institute of Technology",
        academic_term="Autumn Semester 2026",
        time_config=time_config,
        rooms=rooms,
        faculty=faculty,
        batches=batches,
        courses=courses,
        weights=OptimizationWeights(
            weight_idle_student=2.0,
            weight_idle_faculty=1.5,
            weight_workload_balance=1.2,
            weight_room_utilization=1.0,
            weight_faculty_preference=1.5,
        ),
    )


def get_business_school_preset() -> TimetableDataset:
    time_config = TimeConfig(
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        slots_per_day=7,
        slot_times=[
            "09:30 - 10:30",
            "10:30 - 11:30",
            "11:45 - 12:45",
            "12:45 - 13:45 (Lunch)",
            "13:45 - 14:45",
            "14:45 - 15:45",
            "16:00 - 17:00",
        ],
        lunch_slot_idx=3,
        break_slot_indices=[],
    )

    rooms = [
        Room(id="b_hall_a", name="Executive Amphitheater A", room_type=RoomType.LECTURE_HALL, capacity=60, building="Management Wing", floor=1),
        Room(id="b_hall_b", name="Executive Amphitheater B", room_type=RoomType.LECTURE_HALL, capacity=60, building="Management Wing", floor=1),
        Room(id="b_lab", name="FinTech & Bloomberg Lab", room_type=RoomType.LAB_COMPUTER, capacity=45, building="Finance Center", floor=2),
        Room(id="b_sem", name="Boardroom Seminar Suite", room_type=RoomType.SEMINAR_HALL, capacity=50, building="Management Wing", floor=3),
    ]

    faculty = [
        Faculty(id="f_mehta", name="Prof. Arun Mehta", department="Finance", designation="Dean", max_daily_hours=3, max_weekly_hours=12, unavailable_slots=[[0, 0], [4, 5], [4, 6]], preferred_slots=[[1, 1], [2, 1], [3, 1]]),
        Faculty(id="f_kapoor", name="Dr. Simran Kapoor", department="Marketing", designation="Professor", max_daily_hours=4, max_weekly_hours=15, unavailable_slots=[], preferred_slots=[[0, 1], [1, 2], [3, 2]]),
        Faculty(id="f_gupta", name="Dr. Rahul Gupta", department="Analytics", designation="Associate Professor", max_daily_hours=4, max_weekly_hours=16, unavailable_slots=[[2, 4]], preferred_slots=[[0, 0], [2, 1]]),
    ]

    batches = [
        StudentBatch(id="mba_1", name="MBA Year 1 - Cohort Blue", department="Management", semester=1, size=45, preferred_room_id="b_hall_a"),
        StudentBatch(id="mba_2", name="MBA Year 1 - Cohort Gold", department="Management", semester=1, size=42, preferred_room_id="b_hall_b"),
    ]

    courses = [
        Course(id="c_fin", code="MBA101", name="Corporate Finance", department="Finance", weekly_hours=3, credits=3, room_type_required=RoomType.LECTURE_HALL, faculty_ids=["f_mehta"], batch_ids=["mba_1", "mba_2"], color="#059669"),
        Course(id="c_mkt", code="MBA102", name="Strategic Marketing", department="Marketing", weekly_hours=3, credits=3, room_type_required=RoomType.LECTURE_HALL, faculty_ids=["f_kapoor"], batch_ids=["mba_1", "mba_2"], color="#ea580c"),
        Course(id="c_anl", code="MBA103", name="Business Analytics & Modeling", department="Analytics", weekly_hours=3, credits=3, room_type_required=RoomType.LECTURE_HALL, faculty_ids=["f_gupta"], batch_ids=["mba_1", "mba_2"], color="#2563eb"),
        Course(id="c_lab", code="MBA104L", name="Financial Modeling Workshop", department="Finance", course_type=CourseType.LAB, weekly_hours=2, credits=1, consecutive_slots=2, room_type_required=RoomType.LAB_COMPUTER, faculty_ids=["f_mehta"], batch_ids=["mba_1", "mba_2"], color="#0d9488"),
    ]

    return TimetableDataset(
        name="Horizon Graduate School of Business",
        academic_term="Trimester II 2026",
        time_config=time_config,
        rooms=rooms,
        faculty=faculty,
        batches=batches,
        courses=courses,
    )


ALL_PRESETS: Dict[str, Any] = {
    "engineering": get_engineering_preset,
    "business": get_business_school_preset,
}
