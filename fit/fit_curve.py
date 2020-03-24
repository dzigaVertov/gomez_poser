# Fit a bezier curve to a set of points
import bpy
from typing import List
from mathutils import Vector, Matrix
import numpy as np


# Fit the Bezier curves
MAXPOINTS = 10000


def compute_left_tangent(points: List[Vector], end: int) -> Vector:
    """
    Approximate unit tangent at startpoint of digitized curve
    """
    that_1 = points[end+1] - points[end]
    if that_1.length == 0:
        raise ZeroDivisionError
    that_1.normalize()
    return that_1


def compute_right_tangent(points: List[Vector], end: int) -> Vector:
    """
    Approximate unit tangents at endpoints of digitized curve
    """
    that_2 = points[end - 1] - points[end]
    if that_2.length == 0:
        raise ZeroDivisionError
    that_2.normalize()
    return that_2


def compute_center_tangent(points: List[Vector], center: int):
    """
    Approximate unit tangents at center of digitized curve
    """
    v_1 = points[center - 1] - points[center]
    v_2 = points[center] - points[center+1]

    that_center = Vector((0, 0, 0))
    that_center.x = (v_1.x + v_2.x)/2
    that_center.y = (v_1.y + v_2.y)/2
    if that_center.length == 0.0:
        raise ZeroDivisionError

    that_center.normalize()
    return that_center


def bezier_ii(degree: int, ctrl_points: List[Vector], t: float):
    """
    Bezier :
    Evaluate a Bezier curve at a particular parameter value
    """
    j: int
    q: Vector
    v_temp: List[Vector]

    # Copy array of control points
    v_temp = [vec.copy() for vec in ctrl_points]

    # Triangle computation
    for _ in range(1, degree+1):
        for j in range(degree):
            v_temp[j].x = (1-t)*v_temp[j].x + t*v_temp[j+1].x
            v_temp[j].y = (1-t)*v_temp[j].y + t*v_temp[j+1].y

    q = v_temp[0]
    return q


def b_0(u: float) -> float:
    """
    B0  Bezier multiplier
    """
    tmp = 1 - u
    return tmp*tmp*tmp


def b_1(u: float) -> float:
    """
    B1  Bezier multiplier
    """
    tmp = 1-u
    return 3*u*(tmp*tmp)


def b_2(u: float) -> float:
    """
    B2 Bezier multiplier
    """
    tmp = 1-u
    return 3*u*u*tmp


def b_3(u: float) -> float:
    """
    B3  Bezier multiplier
    """
    return u*u*u


def chord_length_parametrize(d: List[Vector], first: int, last: int) -> List[float]:
    """
    Assign parameter values to digitized points
    using relative distances between points.
    """
    i: int
    u = [0.0]*(last-first + 1)

    for i in range(first+1, last+1):
        u[i-first] = u[i-first - 1] + (d[i-1] - d[i]).length

    for i in range(first+1, last+1):
        u[i-first] = u[i-first] / u[last-first]

        return u


def compute_max_error(points: List[Vector], first: int,
                      last: int, bez_curve: List[Vector],
                      u: List[float]) -> (float, int):
    """
       ComputeMaxError :
     Find the maximum squared distance of digitized points
      to fitted curve.

    """
    split_point = (last - first + 1)/2
    max_dist = 0.0
    P: Vector
    for i in range(first+1, last):
        P = bezier_ii(3, bez_curve, u[i-first])
        v = P - points[i]
        dist = v.length_squared

        if dist >= max_dist:
            max_dist = dist
            split_point = i

    return max_dist, split_point


def generate_bezier(points: List[Vector], first: int, last: int, u_prime: List[float], that_1: Vector, that_2: Vector) -> List[Vector]:

    i: int
    a = np.ndarray([MAXPOINTS, 2], dtype=Vector)
    n_pts: int
    C = Matrix([[0, 0], [0, 0]])
    X = Vector((0, 0))
    tmp: Vector
    bez_curve = [Vector((0, 0, 0)) for _ in range(4)]

    n_pts = last - first + 1

    # Compute the A's
    for i in range(n_pts):
        v_1 = that_1
        v_2 = that_2
        v_1 *= b_1(u_prime[i])
        v_2 *= b_2(u_prime[i])
        a[i][0] = v_1
        a[i][1] = v_2

    # Create the C and X matrices
    for i in range(n_pts):
        C.row[0][0] += a[i][0].length_squared
        C.row[0][1] += a[i][0].dot(a[i][1])
        C.row[1][0] = C.row[0][1]
        C.row[1][1] = a[i][1].length_squared

        tmp = (points[first + i] -
               (
                   (points[first] * b_0(u_prime[i])) +
                   (
                       (points[first] * b_1(u_prime[i])) +
                       (
                           (points[last] * b_2(u_prime[i])) +
                           (points[last] * b_3(u_prime[i]))))
        )
        )

        X[0] += a[i, 0].dot(tmp)
        X[1] += a[i, 1].dot(tmp)

        # Compute the determinants of C and X
        det_C0_C1 = C.row[0][0] * C.row[1][1] - C.row[1][0]*C.row[0][1]
        det_C0_X = C.row[0][0] * X[1] - C.row[1][0] * X[0]
        det_X_C1 = X[0] * C.row[1][1] - X[1] * C.row[0][1]

        # Finally, derive alpha values
        alpha_l = 0.0 if det_C0_C1 == 0 else det_X_C1/det_C0_C1
        alpha_r = 0.0 if det_C0_C1 == 0 else det_C0_X/det_C0_C1

        # If alpha negative, use the Wu/Barsky heuristic (see text)
        # (if alpha is 0, you get coincident control points that lead to
        # divide by zero in any subsequent NewtonRaphsonRootFind() call.

        segLength = (points[first] - points[last]).length
        epsilon = 1.0e-6 * segLength

        if alpha_l < epsilon or alpha_r < epsilon:
            # fall back on standard(probably inaccurate) formula,
            # and subdivide further if needed.
            dist = segLength / 3.0
            bez_curve[0] = points[first]
            bez_curve[3] = points[last]
            bez_curve[1] = (that_1 * dist) + bez_curve[0]
            bez_curve[2] = (that_2 * dist) + bez_curve[3]
            return bez_curve

        # First and last control points of the Bezier curve are
        # positioned exactly at the first and last data points
        # Control points 1 and 2 are positioned an alpha distance out
        # on the tangent vectors, left and right, respectively
        bez_curve[0] = points[first]
        bez_curve[3] = points[last]
        bez_curve[1] = (that_1 * alpha_l) + bez_curve[0]
        bez_curve[2] = (that_2 * alpha_r) + bez_curve[3]
        return bez_curve


def newton_root_find(q: List[Vector], p: Vector, u: float) -> float:
    """
    NewtonRaphsonRootFind :
    Use Newton-Raphson iteration to find better root.
    """

    numerator: float
    denominator: float
    q_1 = [Vector() for _ in range(3)]
    q_2 = [Vector() for _ in range(2)]  # Q' and Q''
    q_u: Vector
    q1_u: Vector
    q2_u: Vector  # u evaluated at Q, Q', & Q''
    u_prime: float  # Improved u
    i: int

    # Compute Q(u)
    q_u = bezier_ii(3, q, u)

    # Generate control vertices for Q'
    for i in range(3):
        q_1[i].x = (q[i+1].x - q[i].x) * 3.0
        q_1[i].y = (q[i+1].y - q[i].y) * 3.0

    # Generate control vertices for Q''
    for i in range(2):
        q_2[i].x = (q_1[i+1].x - q_1[i].x) * 2.0
        q_2[i].y = (q_1[i+1].y - q_1[i].y) * 2.0

    # Compute Q'(u) and Q''(u)
    q1_u = bezier_ii(2, q_1, u)
    q2_u = bezier_ii(1, q_2, u)

    # Compute f(u)/f'(u)
    numerator = (q_u.x - p.x) * (q1_u.x) + (q_u.y - p.y) * (q1_u.y)
    denominator = (q1_u.x) * (q1_u.x) + (q1_u.y) * (q1_u.y) + \
        (q_u.x - p.x) * (q2_u.x) + (q_u.y - p.y) * (q2_u.y)
    if denominator == 0.0:
        return u

    #  u = u - f(u)/f'(u)
    u_prime = u - (numerator/denominator)
    return u_prime


def reparametrize(points: List[Vector], first: int, last: int, u: List[float], bez_curve: List[Vector]) -> List[float]:
    """
    Reparameterize:
    Given set of points and their parameterization, try to find
    a better parameterization.
    """
    n_pts = last - first + 1
    i: int
    u_prime = [0.0]*n_pts

    for i in range(first, last+1):
        u_prime[i-first] = newton_root_find(
            bez_curve, points[i], u[i-first])


def fit_cubic(points, first, last, that_1, that_2, error):
    """
    Point[] bezCurve; /*Control points of fitted Bezier curve*/
    double[] u;     /*  Parameter values for point  */
    double[] uPrime;    /*  Improved parameter values */
    double maxError;    /*  Maximum fitting error    */
    int splitPoint; /*  Point to split point set at  */
    int nPts;       /*  Number of points in subset  */
    double iterationError; /*Error below which you try iterating  */
    int maxIterations = 4; /*  Max times to try iterating  */
    Vector tHatCenter;      /* Unit tangent vector at splitPoint */
    int i;
    """
    max_iterations = 4
    iteration_error = error * error
    n_points = last - first + 1

    # Use heuristic if region only has two points in it
    if n_points == 2:
        dist = (points[first] - points[last]).length/3

        bez_curve = [0]*4
        bez_curve[0] = points[first]
        bez_curve[3] = points[last]
        bez_curve[1] = (that_1 * dist) + bez_curve[0]
        bez_curve[2] = (that_2 * dist) + bez_curve[3]

        return bez_curve[1:]

    # Parametrize points, and attempt to fit curve
    u = chord_length_parametrize(points, first, last)
    bez_curve = generate_bezier(
        points, first, last, u, that_1, that_2)

    # Find max deviation of points to fitted curve
    max_error, split_point = compute_max_error(
        points, first, last, bez_curve, u)

    if max_error < iteration_error:
        for i in range(max_iterations):
            u_prime = reparametrize(
                points, first, last, u, bez_curve)
            bez_curve = generate_bezier(
                points, first, last, u_prime, that_1, that_2)
            max_error, split_point = compute_max_error(
                points, first, last, bez_curve, u_prime)

            if max_error < error:
                return bez_curve[1:]

            u = u_prime

    # Fitting failed -- split at max error point and fit recursively
    that_center = compute_center_tangent(points, split_point)
    result = fit_cubic(points, split_point, last,
                       that_center, that_2, error)

    return result


def fit_curve(points, error):
    # Unit tangent vector at endpoint
    that_1 = compute_left_tangent(points, 0)
    # Unit tangent vector at endpoint
    that_2 = compute_right_tangent(points, len(points) - 1)

    result = fit_cubic(
        points, 0, len(points) - 1, that_1, that_2, error)

    return result


if __name__ == "__main__":
    from random import randint
    points = [Vector((randint(1, 10), randint(1, 10), randint(1, 10)))
              for _ in range(20)]
    print(fit_curve(points, 0.01))
