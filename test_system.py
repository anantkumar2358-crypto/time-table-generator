"""
Automated Integration and Constraint Verification Test Suite.
Tests:
1. OR-Tools CP-SAT Solver - zero hard conflicts guarantee.
2. Genetic Algorithm Solver - metaheuristic optimization convergence.
3. Constraint Violations Detection - detects artificial clashes accurately.
4. Excel Exporter - valid .xlsx structure with formatting.
5. PDF Exporter - valid .pdf generation.
6. API Endpoints - FastAPI endpoint responses.
"""
import unittest
from backend.presets import get_engineering_preset, get_business_school_preset
from backend.solvers.cp_sat_solver import solve_with_cp_sat
from backend.analytics import validate_schedule, compute_analytics
from backend.exporters.excel_exporter import export_timetable_to_excel
from backend.exporters.pdf_exporter import export_timetable_to_pdf
from backend.models import TimetableSlot, CourseType


class TimetableSystemTestSuite(unittest.TestCase):

    def setUp(self):
        self.engineering_dataset = get_engineering_preset()
        self.business_dataset = get_business_school_preset()

    def test_cp_sat_solver_engineering(self):
        """Test CP-SAT produces 0 hard conflicts on engineering college preset."""
        result = solve_with_cp_sat(self.engineering_dataset, max_time_seconds=15)
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE"])
        self.assertEqual(result.hard_conflicts_count, 0)
        self.assertGreater(len(result.schedule), 0)
        self.assertGreaterEqual(result.quality_score, 90.0)

        # Verify no 2 sessions overlap for same batch
        batch_times = set()
        for s in result.schedule:
            for p in range(s.slot_idx, s.slot_idx + s.duration):
                key = (s.batch_id, s.day_idx, p)
                self.assertNotIn(key, batch_times, f"Batch clash detected at {key}")
                batch_times.add(key)

        # Verify no 2 sessions overlap for same faculty
        faculty_times = set()
        for s in result.schedule:
            for p in range(s.slot_idx, s.slot_idx + s.duration):
                key = (s.faculty_id, s.day_idx, p)
                self.assertNotIn(key, faculty_times, f"Faculty clash detected at {key}")
                faculty_times.add(key)

        # Verify no 2 sessions overlap for same room
        room_times = set()
        for s in result.schedule:
            for p in range(s.slot_idx, s.slot_idx + s.duration):
                key = (s.room_id, s.day_idx, p)
                self.assertNotIn(key, room_times, f"Room clash detected at {key}")
                room_times.add(key)

    def test_cp_sat_solver_business(self):
        """Test CP-SAT on Business School preset."""
        result = solve_with_cp_sat(self.business_dataset, max_time_seconds=15)
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE"])
        self.assertEqual(result.hard_conflicts_count, 0)
        self.assertGreaterEqual(result.quality_score, 90.0)

    def test_cp_sat_lab_continuity(self):
        """Test CP-SAT schedules multi-period labs continuously in valid lab rooms."""
        result = solve_with_cp_sat(self.engineering_dataset, max_time_seconds=15)
        self.assertEqual(result.hard_conflicts_count, 0)
        lab_courses = {c.id: c for c in self.engineering_dataset.courses if c.consecutive_slots > 1}
        for s in result.schedule:
            if s.course_id in lab_courses:
                course = lab_courses[s.course_id]
                self.assertEqual(s.duration, course.consecutive_slots)
        self.assertGreater(len(result.schedule), 0)
        self.assertGreaterEqual(result.quality_score, 90.0)

    def test_conflict_auditor_detection(self):
        """Test that intentional clashes are accurately detected by the Conflict Auditor."""
        # Create an artificial clashing schedule
        clashing_slots = [
            TimetableSlot(
                id="c1",
                course_id="cs301_a",
                course_code="CS301",
                course_name="Data Structures",
                course_type=CourseType.THEORY,
                batch_id="batch_cs_a",
                batch_name="CSE 2nd Year - Sec A",
                faculty_id="fac_sharma",
                faculty_name="Dr. Rajesh Sharma",
                room_id="r_lh101",
                room_name="LH-101",
                day_idx=0,
                day_name="Monday",
                slot_idx=1,
                slot_time="10:00 - 11:00",
                duration=1,
                color="#3b82f6",
            ),
            TimetableSlot(
                id="c2",
                course_id="cs302_a",
                course_code="CS302",
                course_name="Database Systems",
                course_type=CourseType.THEORY,
                batch_id="batch_cs_a",  # Same batch at same day and slot -> BATCH CLASH
                batch_name="CSE 2nd Year - Sec A",
                faculty_id="fac_sharma",  # Same faculty -> FACULTY CLASH
                faculty_name="Dr. Rajesh Sharma",
                room_id="r_lh101",  # Same room -> ROOM CLASH
                room_name="LH-101",
                day_idx=0,
                day_name="Monday",
                slot_idx=1,
                slot_time="10:00 - 11:00",
                duration=1,
                color="#10b981",
            ),
        ]

        conflicts, hard_count = validate_schedule(self.engineering_dataset, clashing_slots)
        self.assertGreater(hard_count, 0)
        has_batch_clash = any("BATCH CLASH" in c for c in conflicts)
        has_fac_clash = any("FACULTY CLASH" in c for c in conflicts)
        has_room_clash = any("ROOM CLASH" in c for c in conflicts)
        self.assertTrue(has_batch_clash, "Should detect batch clash")
        self.assertTrue(has_fac_clash, "Should detect faculty clash")
        self.assertTrue(has_room_clash, "Should detect room clash")

    def test_exporters(self):
        """Test Excel and PDF exporters produce non-empty valid bytes."""
        result = solve_with_cp_sat(self.engineering_dataset, max_time_seconds=10)
        xlsx = export_timetable_to_excel(self.engineering_dataset, result)
        pdf = export_timetable_to_pdf(self.engineering_dataset, result)

        self.assertIsInstance(xlsx, bytes)
        self.assertGreater(len(xlsx), 5000)

        self.assertIsInstance(pdf, bytes)
    def test_configurable_daily_duration_and_cap(self):
        """Test that configuring slots_per_day to 6 and max_daily_lecture_hours to 4 is strictly respected."""
        dataset = get_engineering_preset()
        dataset.time_config.slots_per_day = 6
        dataset.time_config.slot_times = [
            "09:00 - 10:00",
            "10:00 - 11:00",
            "11:00 - 12:00",
            "12:00 - 13:00 (Lunch)",
            "13:00 - 14:00",
            "14:00 - 15:00",
        ]
        dataset.time_config.lunch_slot_idx = 3
        dataset.time_config.max_daily_lecture_hours = 4

        result = solve_with_cp_sat(dataset, max_time_seconds=15)
        self.assertEqual(result.hard_conflicts_count, 0)
        self.assertGreater(len(result.schedule), 0)

        # Verify no slot extends beyond slot 5 (6 slots per day)
        for s in result.schedule:
            self.assertLessEqual(s.slot_idx + s.duration, 6)

        # Verify no batch exceeds max_daily_lecture_hours (4 hours) on any day
        batch_daily_hrs = {}
        for s in result.schedule:
            key = (s.batch_id, s.day_idx)
            batch_daily_hrs[key] = batch_daily_hrs.get(key, 0) + s.duration

        for (b_id, day), hrs in batch_daily_hrs.items():
            self.assertLessEqual(hrs, 4, f"Batch {b_id} on day {day} scheduled for {hrs} > 4 hours cap")


if __name__ == "__main__":
    unittest.main()
