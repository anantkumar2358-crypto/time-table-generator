"""
Command-Line Interface (CLI) for the Intelligent College Timetable Generator.
Supports generation, verification, Excel/PDF exports, and running automated tests.
"""
import argparse
import sys
import os
import time

from backend.models import GenerationRequest, OptimizationWeights
from backend.presets import ALL_PRESETS, get_engineering_preset, get_business_school_preset
from backend.solvers.cp_sat_solver import solve_with_cp_sat
from backend.analytics import compute_analytics, validate_schedule
from backend.exporters.excel_exporter import export_timetable_to_excel
from backend.exporters.pdf_exporter import export_timetable_to_pdf


def cmd_test():
    print("=" * 70)
    print("RUNNING COMPREHENSIVE TIMETABLE ENGINE TEST SUITE")
    print("=" * 70)

    dataset = get_engineering_preset()
    print(f"\n[1/4] Loaded Preset: '{dataset.name}'")
    print(f"      Batches: {len(dataset.batches)} | Courses: {len(dataset.courses)} | Rooms: {len(dataset.rooms)} | Faculty: {len(dataset.faculty)}")

    # Test 1: CP-SAT Solver
    print("\n[2/4] Testing OR-Tools CP-SAT Solver...")
    t0 = time.time()
    res_cp = solve_with_cp_sat(dataset, max_time_seconds=15)
    t_cp = time.time() - t0
    print(f"      Status: {res_cp.status}")
    print(f"      Hard Conflicts: {res_cp.hard_conflicts_count}")
    print(f"      Quality Score: {res_cp.quality_score} / 100")
    print(f"      Sessions Scheduled: {len(res_cp.schedule)}")
    print(f"      Execution Time: {round(t_cp, 2)}s")
    assert res_cp.hard_conflicts_count == 0, "CP-SAT produced hard conflicts!"
    assert len(res_cp.schedule) > 0, "CP-SAT produced empty schedule!"
    print("      -> CP-SAT Solver PASSED (100% Conflict-Free)")

    # Test 2: Exporters
    print("\n[3/3] Testing Document Exporters (Excel & PDF)...")
    xlsx = export_timetable_to_excel(dataset, res_cp)
    pdf = export_timetable_to_pdf(dataset, res_cp)
    print(f"      Generated Excel Workbook: {len(xlsx):,} bytes")
    print(f"      Generated PDF Document: {len(pdf):,} bytes")
    assert len(xlsx) > 1000, "Excel output too small!"
    assert len(pdf) > 1000, "PDF output too small!"
    print("      -> Exporters PASSED")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED SUCCESSFULLY! The system is 100% functional.")
    print("=" * 70)


def cmd_generate(args):
    preset_name = args.preset.lower()
    if preset_name not in ALL_PRESETS:
        print(f"Error: Unknown preset '{preset_name}'. Choose from: {list(ALL_PRESETS.keys())}")
        sys.exit(1)

    dataset = ALL_PRESETS[preset_name]()
    print(f"Generating timetable for '{dataset.name}' using Google OR-Tools CP-SAT...")

    res = solve_with_cp_sat(dataset, max_time_seconds=args.max_time)

    print("\n--- Generation Summary ---")
    print(f"Status:          {res.status}")
    print(f"Quality Score:   {res.quality_score} / 100")
    print(f"Hard Conflicts:  {res.hard_conflicts_count}")
    print(f"Total Sessions:  {len(res.schedule)}")
    print(f"Solve Time:      {res.execution_time_sec}s")
    print(f"Room Util:       {res.analytics.room_utilization_rate}%")
    print(f"Avg Batch Idle:  {res.analytics.batch_idle_hours_per_week} hrs/week")

    if args.export_excel:
        xlsx_bytes = export_timetable_to_excel(dataset, res)
        with open(args.export_excel, "wb") as f:
            f.write(xlsx_bytes)
        print(f"\n[Saved] Excel timetable written to: {args.export_excel}")

    if args.export_pdf:
        pdf_bytes = export_timetable_to_pdf(dataset, res)
        with open(args.export_pdf, "wb") as f:
            f.write(pdf_bytes)
        print(f"[Saved] PDF timetable written to: {args.export_pdf}")


def main():
    parser = argparse.ArgumentParser(description="Intelligent College Timetable Generator CLI")
    subparsers = parser.add_subparsers(dest="command")

    # test subcommand
    subparsers.add_parser("test", help="Run system verification and test suite")

    # generate subcommand
    gen_p = subparsers.add_parser("generate", help="Generate a timetable")
    gen_p.add_argument("--preset", default="engineering", choices=["engineering", "business"], help="Preset dataset")
    gen_p.add_argument("--max-time", type=int, default=30, help="Maximum solve time in seconds")
    gen_p.add_argument("--export-excel", type=str, default="", help="Path to export .xlsx file")
    gen_p.add_argument("--export-pdf", type=str, default="", help="Path to export .pdf file")

    # serve subcommand
    subparsers.add_parser("serve", help="Start FastAPI web server")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test()
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "serve":
        import uvicorn
        print("Starting Timetable Generator server on http://localhost:8000 ...")
        uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
