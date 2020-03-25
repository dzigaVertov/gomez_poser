import bpy
from mathutils import Matrix, Vector
import pytest
from gomez_poser.fit import fit_curve


# COMPUTE TANGENTS
# -----------------------------------------------------

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

# --------------------------------------------------------------------

# CHORD_LENGTH_PARAMETRIZE
# ---------------------------------------------------------------------

def test_chord_length_par_zero_distance():
    with pytest.raises(ZeroDivisionError):
        points = [Vector((1,1,1)) for _ in range(5)]
        fit_curve.chord_length_parametrize(points, 0, 4)

def test_chord_length_parameter():
    n = 15
    points = [Vector((i,i,i)) for i in range(n)]
    parameter = fit_curve.chord_length_parametrize(points, 0, n-1)
    assert parameter[0] == 0.0
    assert parameter[-1] == 1.0

def test_chord_length_par_equidistant():
    points = [Vector((i,0,0)) for i in range(10)]
    parameter = fit_curve.chord_length_parametrize(points, 0, 9)
    result = [i/8 for i in range(9)]
    assert parameter == result

