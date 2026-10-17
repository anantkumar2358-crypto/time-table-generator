"""
Solvers package for Timetable Generator.
"""
from .cp_sat_solver import solve_with_cp_sat
from .genetic_solver import solve_with_genetic_algorithm

__all__ = ["solve_with_cp_sat", "solve_with_genetic_algorithm"]
