# Fit a bezier curve to a set of points
import mathutils
from mathutils import Vector


class FitCurves:
    # Fit the Bezier curves
    MAXPOINTS = 10000

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

    def fit_curve(points, error):
        # Unit tangent vector at endpoint
        that_1 = compute_left_tangent(points, 0)
        # Unit tangent vector at endpoint
        that_2 = compute_right_tangent(points, len(points) - 1)

        result = fit_cubic(points, 0, len(points) - 1, that_1, that_2, error)

        return result
