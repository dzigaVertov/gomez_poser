# Fit a bezier curve to a set of points
from typing import List
import mathutils
from mathutils import Vector


class FitCurves:
    # Fit the Bezier curves
    MAXPOINTS = 10000

    @staticmethod
    def compute_left_tangent(points: List[mathutils.Vector], end: int) -> Vector:
        that_1 = (points[end+1] - points[end]).normalized()
        return that_1

    @staticmethod
    def fit_cubic(points, first, last, that_1, that_2, error):
        # Point[] bezCurve; /*Control points of fitted Bezier curve*/
        # double[] u;     /*  Parameter values for point  */
        # double[] uPrime;    /*  Improved parameter values */
        # double maxError;    /*  Maximum fitting error    */
        # int splitPoint; /*  Point to split point set at  */
        # int nPts;       /*  Number of points in subset  */
        # double iterationError; /*Error below which you try iterating  */
        # int maxIterations = 4; /*  Max times to try iterating  */
        # Vector tHatCenter;      /* Unit tangent vector at splitPoint */
        # int i;

        iteration_error = error * error
        n_points = last - first + 1

        # Use heuristic if region only has two points in it
        if n_points == 2:
            dist = (points[first] - points[last]).distance()/3

            bez_curve = [0]*4
            bez_curve[0] = points[first]
            bez_curve[3] = points[last]
            bez_curve[1] = (that_1 * dist) + bez_curve[0]
            bez_curve[2] = (that_2 * dist) + bez_curve[3]

            return bez_curve[1:]

        # Parametrize points, and attempt to fit curve
        u = chord_length_parametrize(points, first, last)
        bez_curve = generate_bezier(points, first, last, u, that_1, that_2)

        # Find max deviation of points to fitted curve
        max_error, split_point = compute_max_error(
            points, first, last, bez_curve, u)

        if max_error < iteration_error:
            for i in range(max_iterations):
                u_prime = reparametrize(points, first, last, u, bez_curve)
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

        result = fit_cubic(points, 0, len(points) - 1, that_1, that_2, error)

        return result
