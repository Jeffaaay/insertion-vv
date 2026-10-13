"""Procedural presentation set. All apparatus is illustrative, not hardware evidence."""

import math

import bpy
from mathutils import Vector


def material(name, color, metal=0, rough=0.4):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def finish(obj, name, mat, parent=None, bevel=0):
    obj.name = name
    obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("Machined edges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def box(name, loc, size, mat, parent=None, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, parent, bevel)


def cylinder(name, loc, radius, depth, mat, parent=None, vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = finish(bpy.context.object, name, mat, parent, min(radius * 0.12, 0.025))
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def label(text, loc, size, mat, rotation=(math.pi / 2, 0, 0), parent=None):
    curve = bpy.data.curves.new(text, "FONT")
    curve.body = text
    curve.size = size
    curve.extrude = 0.001
    obj = bpy.data.objects.new(text, curve)
    bpy.context.collection.objects.link(obj)
    obj.location, obj.rotation_euler = loc, rotation
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def empty(name):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    return obj


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPTIX"
    scene.cycles.max_bounces = 6
    scene.render.use_persistent_data = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.13, 0.18, 0.23, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"

    graphite = material("Anodized graphite", (0.035, 0.052, 0.065), 0.7, 0.32)
    steel = material("Brushed titanium", (0.36, 0.45, 0.50), 0.85, 0.23)
    silver = material("Needle polished steel", (0.65, 0.73, 0.78), 0.95, 0.17)
    ceramic = material("Warm ceramic", (0.64, 0.70, 0.70), 0.25, 0.3)
    black = material("Rubber isolation", (0.012, 0.019, 0.023), 0, 0.7)
    teal = material("Teal anodized accent", (0.02, 0.32, 0.31), 0.55, 0.26)
    white = material("Engraved lettering", (0.61, 0.79, 0.77), 0.15, 0.5)
    gold = material("Reference amber", (0.95, 0.4, 0.07), 0.5, 0.24)
    gel = material("Soft-contact sample illustration", (0.09, 0.43, 0.35), 0, 0.28)
    bsdf = gel.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Subsurface Weight"].default_value = 0.15
    bsdf.inputs["Subsurface Radius"].default_value = (0.35, 0.6, 0.45)
    nodes = gel.node_tree.nodes
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 110
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.09
    bump.inputs["Distance"].default_value = 0.009
    gel.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    gel.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    floor = material("Studio floor", (0.032, 0.045, 0.059), 0.3, 0.38)
    box("Studio ground", (0, 0, -3.4), (200, 200, 0.3), floor)
    box("Machine base", (0, 1.25, -2.8), (10, 8, 0.7), graphite, bevel=0.23)
    box("Base rim", (0, 1.25, -2.41), (9.7, 7.7, 0.09), steel, bevel=0.1)
    for x in (-4.2, 4.2):
        for y in (-1.9, 4.3):
            cylinder("Isolation foot", (x, y, -3.21), 0.43, 0.45, black)
            cylinder("Recessed base bolt", (x, y, -2.32), 0.13, 0.08, black, vertices=6)
    # Conceptual vertical stage at the rear. No hardware dimensions are asserted.
    box("Z tower", (0, 3.1, 2.3), (3.8, 1.5, 9.5), graphite, bevel=0.16)
    box("Tower cap", (0, 3.1, 7.1), (4, 1.7, 0.24), ceramic)
    for x in (-1.35, 1.35):
        box("Linear rail", (x, 2.25, 2.45), (0.23, 0.3, 8.6), steel, bevel=0.035)
        for z in (-1, 1, 3, 5, 6.5):
            bolt = cylinder("Rail fastener", (x, 2.05, z), 0.065, 0.09, black, vertices=6)
            bolt.rotation_euler[0] = math.pi / 2
    cylinder("Lead screw", (0, 2.2, 2.3), 0.15, 8.5, silver)
    for z in range(43):
        cylinder("Lead screw thread", (0, 2.2, -1.8 + z * 0.19), 0.19, 0.055, steel, vertices=32)
    label("Z / 01", (-1.25, 2.32, 6.3), 0.34, white)
    # Probe assembly follows recorded needle_z exactly, including the needle tip.
    probe = empty("Recorded needle pose / illustrative tool")
    box("Carriage", (0, 1.9, 4.4), (3.15, 1.05, 1.9), ceramic, probe, 0.12)
    box("Carriage badge", (0, 1.355, 4.65), (1.8, 0.03, 0.45), teal, probe, 0.03)
    label("INSERTION", (-0.72, 1.327, 4.56), 0.16, white, parent=probe)
    box("Probe arm", (0, 0.7, 4), (1.1, 2.9, 0.55), graphite, probe)
    cylinder("Probe collet", (0, 0, 3.55), 0.42, 0.78, steel, probe)
    cylinder("Collet teal band", (0, 0, 3.55), 0.432, 0.18, teal, probe)
    cylinder("Collet nose", (0, 0, 3.1), 0.23, 0.25, graphite, probe)
    cylinder("Illustrative needle shaft", (0, 0, 1.65), 0.085, 2.7, silver, probe)
    bpy.ops.mesh.primitive_cone_add(
        vertices=64, radius1=0, radius2=0.085, depth=0.3, location=(0, 0, 0.15)
    )
    tip = finish(
        bpy.context.object, "Illustrative tip / lowest point is measured qpos", silver, probe
    )
    for poly in tip.data.polygons:
        poly.use_smooth = True
    # Sample holder follows the recorded tissue motion; the rear tower stays fixed.
    sample = empty("Recorded tissue pose / illustrative carrier")
    box("Sample carrier", (0, 0, -1.72), (5.7, 4.2, 0.42), graphite, sample, 0.13)
    box("Carrier polished rim", (0, 0, -1.47), (5.5, 4, 0.09), steel, sample)
    for x in (-2.5, 2.5):
        for y in (-1.7, 1.7):
            cylinder("Sample screw", (x, y, -1.39), 0.095, 0.06, silver, sample, vertices=6)
    for y in (-1.85, 1.85):
        box("Sample retaining lip", (0, y, -1.23), (4.5, 0.13, 0.4), steel, sample, 0.025)
    # A static cutaway reveals penetration into the simplified soft-contact block.
    # Surface remains exactly z=tissue_z; no animated deformation is invented.
    box("Rear sample half", (0, 0.75, -0.68), (4.2, 1.5, 1.36), gel, sample, 0.012)
    front = box(
        "Removable front sample half", (0, -0.75, -0.68), (4.2, 1.5, 1.36), gel, sample, 0.012
    )
    box("Motion platform", (0, 0, -2.1), (3.1, 2.7, 0.32), teal, sample)
    label("SAMPLE / Z", (-1.9, -2.116, -1.8), 0.2, white, parent=sample)
    # A thin amber marker lies in the cutaway plane at the actual target depth.
    for i in range(-10, 11):
        box(
            "300 um depth reference",
            (i * 0.18, 0, -0.3),
            (0.105, 0.018, 0.016),
            gold,
            sample,
            0.005,
        )
    box("Depth rule", (2.18, -0.025, -0.59), (0.028, 0.03, 1.2), steel, sample, 0.006)
    for i in range(7):
        box(
            "Rule tick",
            (2.24, -0.025, -i * 0.2),
            (0.14 if i % 2 == 0 else 0.08, 0.03, 0.012),
            white,
            sample,
            0,
        )
    # Soft studio illumination creates visible edges and metal reflections.
    for name, loc, energy, size, color in (
        ("Large key", (2, -5, 10), 1700, 7, (0.8, 0.9, 1.0)),
        ("Warm rim", (-4, 3, 6), 1500, 5, (1.0, 0.73, 0.48)),
        ("Cool strip", (5, 2, 4), 1250, 4, (0.38, 0.76, 1.0)),
        ("Front fill", (-2, -6, 2), 650, 5, (0.65, 1.0, 0.89)),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.shape, data.size, data.color = energy, "DISK", size, color
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = loc
        aim(obj, (0, 0, 1))
    camera_data = bpy.data.cameras.new("Editorial camera")
    camera = bpy.data.objects.new("Editorial camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.clip_start, camera_data.clip_end = 0.01, 250
    scene.camera = camera
    return scene, camera, probe, sample, front


def set_pose(objects, row, frame):
    scene, camera, probe, sample, front = objects
    probe.location.z = row["needle_z_m"] * 1000
    sample.location.z = row["tissue_z_m"] * 1000
    # Establish the apparatus, then move to a locked macro view before insertion.
    u = min(1, max(0, (frame - 25) / 23)) if frame < 200 else 1
    u = u * u * (3 - 2 * u)
    wide = Vector((10, -15, 10))
    close = Vector((3.5, -10, 4.2))
    target = Vector((0, 0.5, 1.7)).lerp(Vector((0, 0, 0.1)), u)
    camera.location = wide.lerp(close, u)
    camera.data.ortho_scale = 25 * (1 - u) + 7.9 * u
    camera.data.shift_x = -0.08
    aim(camera, target)
    front.hide_render = frame >= 48
    bpy.context.view_layer.update()
