import bpy

curve = bpy.data.objects['curve']
primer_punto =  curve.data.splines[0].bezier_points[0]
segundo_punto = curve.data.splines[0].bezier_points[1]

#posiciones de mundo de los handles
left_handle = curve.matrix_world @ primer_punto.handle_left
right_handle =  curve.matrix_world @ segundo_punto.handle_right

arm = bpy.data.objects['Armature']
ctrl_bone_1 = arm.pose.bones['cola']
ctrl_bone_2 = arm.pose.bones['cabeza']

# quiero llevar el hueso al primer punto.
# 1) convertir la coordenada del primer hueso dal espacio objeto de la armadura.
# 1a) invertir la matriz de mundo de la armadura.
# 1b) obtener las coordenadas de mundo del punto de la curva
# 1b) multiplicar la inversa por el vector posición del punto. 
# 2) asignar la coordenada al hueso.

arm_inv = arm.matrix_world.inverted() # invertir matriz de mundo de armature
new_co_1 = ctrl_bone_1.matrix.inverted() @ arm_inv @ left_handle # point in bone space
new_co_2 = ctrl_bone_2.matrix.inverted() @ arm_inv @ right_handle

ctrl_bone_1.matrix[:3][3] = new_co_1
#ctrl_bone_1.head = new_co_1
ctrl_bone_2.location += new_co_2

# bone.location es es en un espacio del hueso.
# bone.matrix es la matriz de transformación del bone.head en el espacio objeto. 
# bone.head es la posicion de head en el espacio objeto
# bone.matrix_basis es la matriz de transformación del hueso desde la pose_origen
# edit_bone.matrix_local es la matriz de transformación del hueso en pose_origen en el espacio de su hueso padre o del objeto

# quiere decir que para obtener la posición mundo del centro del bone
# hay que hacer A * bone.location  donde A es la matriz del objeto

