"""
Solvers package for Timetable Generator.
"""
from .cp_sat_solver import solve_with_cp_sat

__all__ = ["solve_with_cp_sat"]
