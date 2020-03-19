# Fit a bezier curve to a set of points
from typing import List
import mathutils
from mathutils import Vector


class FitCurves:
    # Fit the Bezier curves
    MAXPOINTS = 10000

    @staticmethod
    def compute_left_tangent(points: List[Vector], end: int) -> Vector:
        that_1 = points[end+1] - points[end]
        that_1.normalize()
        return that_1

    @staticmethod
    def compute_right_tangent(points: List[Vector], end: int) -> Vector:
        that_2 = points[end - 1] - points[end]
        that_2.normalize()
        return that_2

    @staticmethod
    def compute_center_tangent(points: List[Vector], center: int):
        V1 = points[center - 1] - points[center]
        V2 = points[center] - points[center+1]

        that_center = Vector((0, 0, 0))
        that_center.x = (V1.x + V2.x)/2
        that_center.y = (V1.y + V2.y)/2
        that_center.normalize()
        return that_center

    @staticmethod
    def bezier_ii(degree: int, points: List[Vector], t: float):
        """
          Bezier :
              Evaluate a Bezier curve at a particular parameter value

        """

    @staticmethod
    def compute_max_error(points: List(Vector), first: int,
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
