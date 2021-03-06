import bpy
from mathutils.noise import noise
from mathutils import Vector
from gomez_poser import fit

C = bpy.context
D = bpy.data
N=50
scale = 1/10
z_scale = 3
error = 1

def create_spline(spline_ob, b_points):
    n_ctrl_points = int((len(b_points) + 2)/3)
    
    new_spline = spline_ob.data.splines.new('BEZIER')
    new_spline.bezier_points.add(n_ctrl_points)

    # control points will be 0,3,6,9, 12, all multiples of 3
    for i in range(n_ctrl_points):
        ctrl_point = new_spline.bezier_points[i]
        ctrl_point.co = b_points[3*i]
        if i>0:
            l_handle = b_points[3*i - 1]
            ctrl_point.handle_left.xyz = l_handle
        if i<(n_ctrl_points -1):
            r_handle = b_points[3*i +1]
            ctrl_point.handle_right.xyz = r_handle
            


def mostrame(active_frame, points, mat_idx=0, width=50):
    """
    Creates a grease pencil stroke in a given active frame
    """
    n = len(points)
    stroke = active_frame.strokes.new()
    stroke.material_index = mat_idx
    stroke.points.add(n)

    for i in range(n):
        stroke.points[i].co = points[i]
    stroke.line_width = width
    stroke.display_mode = '3DSPACE'

def create_perlin_points(num_points, x_scale=scale, z_scale=z_scale):
    return [ Vector( (i * x_scale, 0, z_scale*noise(Vector(( i * x_scale, 0,0))))) for i in range(N)]
    
ob = C.object
layer = ob.data.layers.active
try:
    active_frame = layer.frames.new(C.scene.frame_current, active=True)
except:
    active_frame = layer.active_frame


stroke = active_frame.strokes.new()
stroke.points.add(N)

points = create_perlin_points(N)

for i in range(N):
    stroke.points[i].co = points[i]
    
stroke.line_width = 50
stroke.display_mode = '3DSPACE'

fitted= fit.fit_curve.fit_curve(points, error = error)

create_spline(C.scene.objects['BezierCurve'], fitted)


#for i in range(len(fitted)):
#    stroke_2.points[i].co = fitted[i]
#    
#stroke_2.line_width = 50
#stroke_2.display_mode = '3DSPACE'



# p_tan1 = [points[0], points[0] + that_1]
# p_tan2 = [points[-1], points[-1] + that_2]
# mostrame(active_frame, p_tan1, mat_idx=2, width=10)
# mostrame(active_frame, p_tan2, mat_idx=2, width=10)
