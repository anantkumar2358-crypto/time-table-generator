# Intelligent College Timetable Generator

An automated, conflict-free college and university timetabling system powered by **Google OR-Tools CP-SAT (Exact Constraint Programming)** and an **Adaptive Genetic Algorithm (Evolutionary Metaheuristic)**.

The system simultaneously balances faculty availability, classroom capacities, student batches, course weekly quotas, continuous lab blocks, and multi-objective soft optimization goals (minimizing student and instructor idle gaps, balancing daily workloads, and maximizing classroom utilization).

---

## 🌟 Key Capabilities & Features

- **Dual-Engine Intelligent Solver**:
  - **Google OR-Tools CP-SAT Solver**: Mathematically provably optimal constraint programming engine guaranteeing **0 hard constraint clashes**.
  - **Advanced Genetic Algorithm**: Evolutionary metaheuristic with domain-aware repair mutation and elitism for flexible Pareto optimization.
- **Strict Hard Constraint Enforcement**:
  - **No Faculty Double-Booking**: An instructor cannot be in two classrooms at the same time.
  - **No Student Batch Double-Booking**: A student section cannot attend two lectures simultaneously.
  - **No Room Overlap**: A classroom or lab can host at most one class per time period.
  - **Classroom Seating Capacity**: Rooms are strictly verified to ensure $\text{capacity} \ge \text{batch size}$.
  - **Room Type Matching**: Laboratory sessions (Computer, Electronics, Physics) are strictly routed to matching lab facilities, and theory classes to lecture halls.
  - **Faculty Availability & Blackout Windows**: Respects designated unavailable hours (e.g., department meetings, research blocks).
  - **Consecutive Multi-Period Blocks**: 2-hour or 3-hour lab sessions are scheduled as contiguous blocks on the same day without crossing lunch or day boundaries.
  - **Faculty Daily Workload Limits**: Caps max daily teaching hours per instructor.
- **Multi-Objective Soft Optimization**:
  - **Minimizing Student Idle Gaps**: Eliminates awkward gaps between morning and afternoon lectures.
  - **Minimizing Faculty Idle Wait Time**: Consolidates instructor schedules.
  - **Daily Workload Balancing**: Distributes course lectures evenly across Monday–Friday.
  - **Maximizing Resource Utilization**: Compact classroom and laboratory scheduling.
  - **Faculty Preferred Slots**: Prioritizes scheduling professors during their preferred time windows.
- **Interactive Web Studio**:
  - Perspective switching: **Batch Timetable**, **Faculty Schedules**, and **Room Occupancy**.
  - **Conflict Auditor**: Automated audit engine verifying every constraint with live clash reporting.
  - **Interactive Slot Move & Swap**: Click any class card to preview or move slots with real-time clash re-validation.
  - **Optimization Weight Tuning**: Interactive sliders to adjust optimization priorities in real time.
- **Multi-Format Document Exports**:
  - **Excel (.xlsx)**: Formatted, color-coded multi-tab workbook with Executive Summary, Batch grids, Faculty schedules, and Room occupancy.
  - **PDF (.pdf)**: Publication-grade landscape timetable report designed with ReportLab.

---

## 📁 System Architecture

```
time-table-generator/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI REST API & static web serving
│   ├── models.py                # Pydantic schemas (Rooms, Faculty, Batches, Courses, Slots)
│   ├── analytics.py             # Conflict auditor & quality score computation
│   ├── presets.py               # Real-world college datasets (Engineering, Business)
│   ├── solvers/
│   │   ├── __init__.py
│   │   ├── cp_sat_solver.py     # Google OR-Tools CP-SAT exact formulation
│   │   └── genetic_solver.py    # Evolutionary metaheuristic with smart repair
│   └── exporters/
│       ├── __init__.py
│       ├── excel_exporter.py    # OpenPyXL-based multi-sheet workbook generator
│       └── pdf_exporter.py      # ReportLab-based landscape PDF generator
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React interactive studio dashboard
│   │   ├── index.css            # Modern utility stylesheet
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── cli.py                       # Command-line interface for headless generation & tests
├── test_system.py               # Comprehensive unit & integration test suite
├── run.py                       # One-click launcher for the full web application
└── README.md
```

---

## 🚀 Quickstart & Usage

### 1. Run the Full Web Application (One-Click)

Launch the integrated web application (FastAPI backend + React frontend):

```powershell
python run.py
```

Open your browser to:
- **Interactive Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive REST API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. Run via Command-Line Interface (CLI)

Generate a conflict-free timetable and export directly to Excel and PDF:

```powershell
# Generate Engineering timetable using OR-Tools CP-SAT
python cli.py generate --preset engineering --solver cp_sat --export-excel timetable.xlsx --export-pdf timetable.pdf

# Generate Business School timetable using Genetic Algorithm
python cli.py generate --preset business --solver genetic --export-excel mba_timetable.xlsx
```

---

### 3. Run the Automated Verification Test Suite

Run the full constraint verification and regression test suite:

```powershell
python test_system.py
```

Or via CLI:
```powershell
python cli.py test
```

---

## 📊 Pre-Configured Academic Presets

1. **Apex Institute of Technology (Engineering & Computing)**:
   - 4 Batches: CSE 2nd Year (Sections A & B), AI & Data Science, ECE 3rd Year.
   - 18 Courses: Data Structures, Database Systems, Machine Learning, Operating Systems, Digital Signal Processing, plus 2-hour lab blocks.
   - 8 Facilities: Lecture Theaters, Standard Classrooms, GPU AI Labs, Systems Computing Labs, Electronics Circuits Lab, Seminar Hall.
   - 6 Faculty: Professors, Associate Professors, and HOD with meeting blackout slots and time preferences.

2. **Horizon Graduate School of Business (Management & Finance)**:
   - 2 MBA Cohorts: Cohort Blue and Cohort Gold.
   - Courses: Corporate Finance, Strategic Marketing, Business Analytics, and Financial Modeling Workshop.
   - Facilities: Executive Amphitheaters, FinTech Bloomberg Lab, Boardroom Suites.

---

## ⚙️ REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status |
| `GET` | `/api/presets` | List of available academic presets |
| `GET` | `/api/preset/{id}` | Get full dataset schema for a preset |
| `POST` | `/api/generate` | Generate timetable using CP-SAT or Genetic Algorithm |
| `POST` | `/api/validate` | Audit an existing or edited schedule for conflicts |
| `POST` | `/api/swap-slot` | Move or swap a class slot with real-time clash check |
| `POST` | `/api/export/excel` | Download timetable as formatted Excel (.xlsx) |
| `POST` | `/api/export/pdf` | Download timetable as publication-ready PDF (.pdf) |
