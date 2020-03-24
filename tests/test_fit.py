import bpy
from mathutils import Matrix, Vector
import pytest
from gomez_poser.fit import fit_curve


def test_compute_left_zero_tangent_vector():
    with pytest.raises(ZeroDivisionError):
        points = [Vector((1, 1, 1)) for _ in range(3)]
        fit_curve.compute_left_tangent(points, 1)


def test_compute_left_simple():
    points = [Vector((1, 0, 0)), Vector((0, 0, 0)), Vector((0, 0, 0))]
    assert fit_curve.compute_left_tangent(
        points, 0) == Vector((-1.0, 0.0, 0.0))


def test_compute_right_zero_tangent_vector():
    with pytest.raises(ZeroDivisionError):
        points = [Vector((1, 1, 1)) for _ in range(3)]
        fit_curve.compute_right_tangent(points, 1)


def test_compute_right_simple():
    points = [Vector((1, 0, 0)), Vector((0, 0, 0)), Vector((0, 0, 0))]
    assert fit_curve.compute_right_tangent(
        points, 1) == Vector((1.0, 0.0, 0.0))


def test_compute_center_zero_tangent_vector():
    with pytest.raises(ZeroDivisionError):
        points = [Vector((1, 1, 1)) for _ in range(3)]
        fit_curve.compute_center_tangent(points, 1)


def test_compute_center_simple():
    points = [Vector((1, 0, 0)), Vector((0, 0, 0)), Vector((0, 0, 0))]
    assert fit_curve.compute_center_tangent(
        points, 1) == Vector((1.0, 0.0, 0.0))
