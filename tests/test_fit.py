import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import interpolate_bezier
import pytest
from gomez_poser.fit import fit_curve
from random import randint, randrange, sample
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


# --------------------------------------------------------------------

# bezier_ii
# ---------------------------------------------------------------------
    
def test_bezier_t0():
    rand_degree = randint(1,10)
    ctrl_points = [Vector(tuple(sample(range(100), 3))) for _ in range(rand_degree+1)]
    assert fit_curve.bezier_ii(rand_degree, ctrl_points, 0) == ctrl_points[0]
    
def test_bezier_t1():
    rand_degree = randint(1,10)
    ctrl_points = [Vector(tuple(sample(range(100), 3))) for _ in range(rand_degree+1)]

    assert fit_curve.bezier_ii(rand_degree, ctrl_points, 1) == ctrl_points[-1]
    
def test_bezier_blender():
    degree = 3
    ctrl_points = [Vector(tuple(sample(range(100), 3))) for _ in range(degree+1)]
    value = interpolate_bezier(ctrl_points[0], ctrl_points[1], ctrl_points[2], ctrl_points[3], 10001)[5000]
    for i in range(3):
        assert fit_curve.bezier_ii(degree, ctrl_points, .5)[i] == pytest.approx(value[i], 0.001)
    
