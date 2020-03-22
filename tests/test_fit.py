import bpy
from mathutils import Matrix, Vector
import pytest
from fit import fit_curve


def test_compute_left():
    points = [Vector((i, i, i)) for i in range(4)]
    assert fit_curve.compute_left_tangent(points, 2) =
