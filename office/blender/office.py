# 니트 인형 사무실 — 블렌더 절차적 장면 (blender -b -P office.py -- out.png [scale%])
import bpy, math, sys
from math import radians as R

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "/tmp/bl/office.png"
PCT = int(argv[1]) if len(argv) > 1 else 50
SAMPLES = int(argv[2]) if len(argv) > 2 else 48

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ── 재질 ──────────────────────────────────────────────────────────────
def mat(name, color, rough=0.6, sheen=0.0, metal=0.0, emit=None, knit=False, wood=False, ss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; n = nt.nodes; l = nt.links
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
        b.inputs["Sheen Roughness"].default_value = 0.5
    if ss:
        b.inputs["Subsurface Weight"].default_value = ss
        b.inputs["Subsurface Radius"].default_value = (0.05, 0.05, 0.05)
    if emit:
        b.inputs["Emission Color"].default_value = (*emit[0], 1)
        b.inputs["Emission Strength"].default_value = emit[1]
    if knit:
        # 니트 코: 줄(z) 방향 사인 + |x 반복| 로 V자 → 범프
        tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ")
        l.new(tc.outputs["Object"], sep.inputs[0])
        cols, rows = knit
        mx = n.new("ShaderNodeMath"); mx.operation = "MULTIPLY"; mx.inputs[1].default_value = cols
        l.new(sep.outputs["X"], mx.inputs[0])
        fr = n.new("ShaderNodeMath"); fr.operation = "FRACT"; l.new(mx.outputs[0], fr.inputs[0])
        sub = n.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 0.5; l.new(fr.outputs[0], sub.inputs[0])
        ab = n.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; l.new(sub.outputs[0], ab.inputs[0])
        mz = n.new("ShaderNodeMath"); mz.operation = "MULTIPLY"; mz.inputs[1].default_value = rows; l.new(sep.outputs["Z"], mz.inputs[0])
        ad = n.new("ShaderNodeMath"); ad.operation = "MULTIPLY_ADD"; ad.inputs[1].default_value = 1.6
        l.new(ab.outputs[0], ad.inputs[0]); l.new(mz.outputs[0], ad.inputs[2])
        fr2 = n.new("ShaderNodeMath"); fr2.operation = "FRACT"; l.new(ad.outputs[0], fr2.inputs[0])
        pw = n.new("ShaderNodeMath"); pw.operation = "SINE"
        mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = math.pi
        l.new(fr2.outputs[0], mul.inputs[0]); l.new(mul.outputs[0], pw.inputs[0])
        bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.55; bump.inputs["Distance"].default_value = 0.02
        l.new(pw.outputs[0], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
        # 코 사이 골은 살짝 어둡게
        ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*[c * 0.78 for c in color], 1); ramp.color_ramp.elements[1].color = (*color, 1)
        l.new(pw.outputs[0], ramp.inputs[0]); l.new(ramp.outputs[0], b.inputs["Base Color"])
    if wood:
        br = n.new("ShaderNodeTexBrick"); br.offset = 0.5
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Color1"].default_value = (*color, 1)
        br.inputs["Color2"].default_value = (*[c * 0.93 for c in color], 1)
        br.inputs["Mortar"].default_value = (*[c * 0.8 for c in color], 1)
        br.inputs["Mortar Size"].default_value = 0.004
        br.inputs["Brick Width"].default_value = 1.2; br.inputs["Row Height"].default_value = 0.18
        tc = n.new("ShaderNodeTexCoord"); l.new(tc.outputs["Object"], br.inputs["Vector"])
        l.new(br.outputs["Color"], b.inputs["Base Color"])
    return m

def hexc(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

M = {
    "floor": mat("floor", hexc("#e2c49b"), 0.55, wood=True),
    "wall": mat("wall", hexc("#f1eee9"), 0.9),
    "wall2": mat("wall2", hexc("#e8e4dd"), 0.9),
    "white": mat("white", hexc("#f4f2ee"), 0.35),
    "gray": mat("gray", hexc("#8d9096"), 0.45, metal=0.3),
    "dark": mat("dark", hexc("#2e3136"), 0.3),
    "screen": mat("screen", hexc("#1d2228"), 0.2, emit=(hexc("#b9d4e6"), 0.6)),
    "chair": mat("chair", hexc("#a9adb3"), 0.8, sheen=0.4),
    "pot": mat("pot", hexc("#d9b48c"), 0.6),
    "leaf": mat("leaf", hexc("#4f8a4a"), 0.5, ss=0.1),
    "rug": mat("rug", hexc("#dcdad6"), 0.95, sheen=0.6),
    "sofa": mat("sofa", hexc("#ece6dc"), 0.9, sheen=0.7),
    "cork": mat("cork", hexc("#c49a6c"), 0.9),
    "paper": mat("paper", hexc("#fbfaf6"), 0.7),
    "window": mat("window", hexc("#dfeef7"), 0.1, emit=(hexc("#eef6fb"), 1.2)),
    "wood2": mat("wood2", hexc("#c8a27a"), 0.5),
    # 니트
    "knit": mat("knit", hexc("#efe6d6"), 0.85, sheen=1.0, knit=(28, 34), ss=0.05),
    "eye": mat("eye", hexc("#1b1b1b"), 0.2),
    "cheek": mat("cheek", hexc("#f2a9a0"), 0.9, sheen=0.5),
}
def knitc(name, h):
    return mat("knit_" + name, hexc(h), 0.85, sheen=1.0, knit=(28, 34), ss=0.05)

# ── 도형 도우미 ────────────────────────────────────────────────────────
def box(name, size, loc, m, bevel=0.01, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        b = o.modifiers.new("b", "BEVEL"); b.width = bevel; b.segments = 3
    o.data.materials.append(m); bpy.ops.object.shade_smooth(); return o

def cyl(name, r, h, loc, m, rot=(0, 0, 0), v=24):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot, vertices=v)
    o = bpy.context.object; o.name = name; o.data.materials.append(m); bpy.ops.object.shade_smooth(); return o

def sph(name, r, loc, m, scale=(1, 1, 1), seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.object; o.name = name; o.scale = scale; o.data.materials.append(m); bpy.ops.object.shade_smooth(); return o

def capsule(name, r, length, a, b_, m):
    """a→b 를 잇는 둥근 막대(팔·다리)."""
    import mathutils
    A = mathutils.Vector(a); B = mathutils.Vector(b_); mid = (A + B) / 2; d = B - A
    o = cyl(name, r, d.length, mid, m)
    o.rotation_mode = "QUATERNION"; o.rotation_quaternion = d.to_track_quat("Z", "Y")
    sph(name + "_e1", r, A, m); sph(name + "_e2", r, B, m)
    return o

# ── 방 ───────────────────────────────────────────────────────────────
RX, RY = 10.0, 8.0
box("floor", (RX, RY, 0.12), (RX / 2, RY / 2, -0.06), M["floor"], 0.02)
box("wall_back", (RX, 0.14, 3.0), (RX / 2, RY + 0.07, 1.5), M["wall"], 0.01)
box("wall_left", (0.14, RY, 3.0), (-0.07, RY / 2, 1.5), M["wall2"], 0.01)
box("base_b", (RX, 0.03, 0.1), (RX / 2, RY - 0.015, 0.05), M["white"], 0.005)
box("base_l", (0.03, RY, 0.1), (0.015, RY / 2, 0.05), M["white"], 0.005)
for i, y in enumerate((1.4, 3.6, 5.8)):          # 왼쪽 벽 창
    box(f"win{i}", (0.05, 1.6, 1.6), (0.02, y, 1.55), M["window"], 0.0)
    box(f"winf{i}", (0.08, 1.7, 0.06), (0.04, y, 0.72), M["white"], 0.005)
# 뒷벽 장식: 코르크판, 달력, 시계, 선반
box("cork", (1.6, 0.04, 1.0), (6.2, RY - 0.02, 1.6), M["cork"], 0.01)
for k, (x, z) in enumerate(((5.75, 1.75), (6.15, 1.55), (6.6, 1.8), (6.35, 1.3))):
    box(f"note{k}", (0.28, 0.02, 0.22), (x, RY - 0.05, z), mat(f"note{k}", hexc(["#f6e7a6", "#cfe8f3", "#f5d0d6", "#d9f0d4"][k]), 0.8), 0.0)
box("cal", (0.9, 0.03, 1.1), (8.3, RY - 0.02, 1.6), M["paper"], 0.005)
for r_ in range(5):
    for c_ in range(6):
        box(f"calc{r_}{c_}", (0.1, 0.01, 0.1), (7.95 + c_ * 0.14, RY - 0.045, 1.85 - r_ * 0.16), M["wall2"], 0.0)
cyl("clock", 0.28, 0.05, (9.5, RY - 0.03, 2.05), M["white"], rot=(R(90), 0, 0))
box("clockh", (0.02, 0.01, 0.16), (9.5, RY - 0.06, 2.1), M["dark"], 0.0)
box("clockm", (0.14, 0.01, 0.02), (9.56, RY - 0.06, 2.05), M["dark"], 0.0)
box("shelf", (1.2, 0.3, 0.04), (3.2, RY - 0.15, 1.75), M["wood2"], 0.01)
for k in range(5):
    box(f"book{k}", (0.07, 0.22, 0.26 + 0.03 * (k % 2)), (2.8 + k * 0.09, RY - 0.17, 1.9), mat(f"bk{k}", hexc(["#c9d6e3", "#e6c9c9", "#e9e1c6", "#cfe1cf", "#d8d0e6"][k]), 0.7), 0.004)
box("rug", (3.2, 2.6, 0.015), (8.1, 1.7, 0.008), M["rug"], 0.02)

# ── 가구 ─────────────────────────────────────────────────────────────
def desk(x, y, rot=0):
    s = math.sin(rot); c = math.cos(rot)
    P = lambda dx, dy: (x + dx * c - dy * s, y + dx * s + dy * c)
    box("desk", (1.3, 0.7, 0.04), (*P(0, 0), 0.72), M["white"], 0.008, rot=(0, 0, rot))
    for dx in (-0.6, 0.6):
        box("leg", (0.04, 0.62, 0.03), (*P(dx, 0), 0.04), M["gray"], 0.005, rot=(0, 0, rot))
        box("leg", (0.04, 0.04, 0.7), (*P(dx, 0), 0.36), M["gray"], 0.005, rot=(0, 0, rot))
    box("mon", (0.56, 0.03, 0.34), (*P(0, 0.2), 1.02), M["screen"], 0.008, rot=(0, 0, rot))
    box("monb", (0.58, 0.02, 0.36), (*P(0, 0.22), 1.02), M["dark"], 0.008, rot=(0, 0, rot))
    box("mons", (0.04, 0.04, 0.14), (*P(0, 0.25), 0.8), M["dark"], 0.004, rot=(0, 0, rot))
    box("monf", (0.18, 0.12, 0.012), (*P(0, 0.25), 0.745), M["dark"], 0.004, rot=(0, 0, rot))
    box("kb", (0.38, 0.12, 0.015), (*P(0, -0.05), 0.75), M["white"], 0.003, rot=(0, 0, rot))
    box("mouse", (0.05, 0.08, 0.02), (*P(0.3, -0.05), 0.75), M["white"], 0.008, rot=(0, 0, rot))
    box("mug", (0.07, 0.07, 0.09), (*P(-0.45, 0.05), 0.785), M["paper"], 0.01, rot=(0, 0, rot))

def chair(x, y, rot=0):
    s = math.sin(rot); c = math.cos(rot)
    P = lambda dx, dy: (x + dx * c - dy * s, y + dx * s + dy * c)
    box("seat", (0.46, 0.44, 0.08), (*P(0, 0), 0.46), M["chair"], 0.03, rot=(0, 0, rot))
    box("back", (0.44, 0.07, 0.48), (*P(0, -0.22), 0.78), M["chair"], 0.03, rot=(R(-8), 0, rot))
    cyl("gas", 0.025, 0.36, (*P(0, 0), 0.24), M["gray"])
    for k in range(5):
        a = rot + k * 2 * math.pi / 5
        box("spoke", (0.3, 0.04, 0.03), (x + 0.15 * math.cos(a), y + 0.15 * math.sin(a), 0.06), M["dark"], 0.008, rot=(0, 0, a))
        sph("wheel", 0.03, (x + 0.29 * math.cos(a), y + 0.29 * math.sin(a), 0.03), M["dark"])

def plant(x, y, big=True):
    h = 0.42 if big else 0.22
    cyl("pot", 0.2 if big else 0.12, h, (x, y, h / 2), M["pot"])
    import random; rnd = random.Random(int(x * 100 + y))
    for k in range(9 if big else 5):
        a = rnd.uniform(0, 6.28); r_ = rnd.uniform(0.05, 0.25 if big else 0.12); z = h + rnd.uniform(0.25, 0.9 if big else 0.35)
        sph("leaf", rnd.uniform(0.12, 0.2) if big else 0.09, (x + r_ * math.cos(a), y + r_ * math.sin(a), z), M["leaf"], scale=(1.4, 0.5, 0.9))

# 책상 섬 두 개(마주 보기) — 사람은 의자에 앉아 모니터를 본다
SEATS = []
for (ox, oy) in ((2.4, 3.4), (5.4, 3.4)):
    for k, dx in enumerate((-0.7, 0.7)):
        desk(ox + dx, oy + 0.45, 0); chair(ox + dx, oy - 0.25, R(180)); SEATS.append((ox + dx, oy - 0.25, R(180)))
        desk(ox + dx, oy + 1.55, R(180)); chair(ox + dx, oy + 2.25, 0); SEATS.append((ox + dx, oy + 2.25, 0))
# 라운지
box("sofa_base", (2.0, 0.85, 0.42), (8.2, 0.9, 0.21), M["sofa"], 0.08)
box("sofa_back", (2.0, 0.25, 0.75), (8.2, 1.3, 0.48), M["sofa"], 0.1)
box("sofa_armL", (0.22, 0.85, 0.6), (7.15, 0.9, 0.3), M["sofa"], 0.08)
box("sofa_armR", (0.22, 0.85, 0.6), (9.25, 0.9, 0.3), M["sofa"], 0.08)
for k, x in enumerate((7.7, 8.7)):
    box("cush", (0.92, 0.7, 0.14), (x, 0.82, 0.48), M["sofa"], 0.06)
cyl("ctable", 0.45, 0.04, (8.0, 2.4, 0.4), M["white"]); cyl("ctleg", 0.04, 0.38, (8.0, 2.4, 0.19), M["gray"])
box("wb", (1.8, 0.05, 1.0), (1.6, RY - 0.08, 1.45), M["white"], 0.01)
box("wbf", (1.86, 0.06, 1.06), (1.6, RY - 0.06, 1.45), M["gray"], 0.01)
plant(0.5, 7.4); plant(9.4, 7.3); plant(9.5, 2.6, False); plant(4.0, 7.5, False); plant(6.95, 1.95)
box("cabinet", (1.4, 0.45, 0.8), (4.3, RY - 0.28, 0.4), M["wood2"], 0.02)
sph("lamp", 0.12, (4.75, RY - 0.28, 0.95), M["paper"])

# ── 니트 인형 ─────────────────────────────────────────────────────────
import mathutils
DS = 1.35   # 인형 크기(책상 대비 꼬마 인형 비율)
def doll(x, y, rot, pose="sit", hat="#9db8d6", scarf=None, held=None):
    """니트 인형 한 명. rot=바라보는 방향(라디안, 0=+y). pose: sit·stand·walk."""
    before = set(bpy.data.objects)
    knit = M["knit"]; hatm = knitc(hat, hat); sc_ = knitc((scarf or hat) + "s", scarf or hat)
    s = math.sin(rot); c = math.cos(rot)
    def P(dx, dy, z): return (x + dx * c - dy * s, y + dx * s + dy * c, z)
    hip = 0.52 / DS if pose == "sit" else 0.42
    body = sph("body", 0.17, P(0, 0, hip + 0.16), knit, scale=(1.0, 0.85, 1.15))
    head = sph("head", 0.19, P(0, 0, hip + 0.47), knit, scale=(1.05, 1.0, 0.95))
    # 모자(골지 띠 + 둥근 몸통 + 방울)
    sph("hat", 0.195, P(0, -0.005, hip + 0.53), hatm, scale=(1.06, 1.04, 0.85))
    cyl("hatband", 0.2, 0.07, P(0, 0, hip + 0.5), hatm)
    sph("pom", 0.06, P(0, -0.01, hip + 0.72), hatm)
    if scarf: cyl("scarf", 0.15, 0.06, P(0, 0, hip + 0.3), sc_)
    # 얼굴(앞쪽 = +y 방향)
    for e in (-0.065, 0.065):
        sph("eye", 0.022, P(e, 0.172, hip + 0.47), M["eye"])
        sph("cheek", 0.03, P(e * 1.6, 0.16, hip + 0.42), M["cheek"], scale=(1, 0.4, 0.7))
    # 팔·다리
    if pose == "sit":
        for sgn in (-1, 1):
            capsule("thigh", 0.065, 0, P(sgn * 0.08, 0.0, hip + 0.03), P(sgn * 0.08, 0.26, hip + 0.03), knit)
            capsule("shin", 0.06, 0, P(sgn * 0.08, 0.28, hip + 0.02), P(sgn * 0.08, 0.32, 0.12), knit)
            capsule("arm", 0.05, 0, P(sgn * 0.17, 0.0, hip + 0.27), P(sgn * 0.12, 0.3, hip + 0.24), knit)
    else:
        swing = 0.12 if pose == "walk" else 0.0
        for sgn in (-1, 1):
            capsule("leg", 0.065, 0, P(sgn * 0.08, 0, hip), P(sgn * 0.08, sgn * swing, 0.06), knit)
            if held:
                capsule("arm", 0.05, 0, P(sgn * 0.17, 0, hip + 0.27), P(sgn * 0.12, 0.2, hip + 0.22), knit)
            else:
                capsule("arm", 0.05, 0, P(sgn * 0.17, 0, hip + 0.27), P(sgn * 0.2, -sgn * swing, hip + 0.05), knit)
        if held:
            box("papers", (0.26, 0.2, 0.08), P(0, 0.24, hip + 0.24), M["paper"], 0.005, rot=(0, 0, rot))
    for o in set(bpy.data.objects) - before:   # 발밑(x, y, 0)을 기준으로 키운다
        o.location = (x + (o.location.x - x) * DS, y + (o.location.y - y) * DS, o.location.z * DS)
        o.scale = tuple(v * DS for v in o.scale)

TEAM = {"research": "#8fb3d9", "edit": "#9cc4a6", "review": "#e3a28f", "pr": "#e7a9c4", "art": "#e9c48f", "voice": "#b9a6d9"}
# 앉아서 일하는 인형(의자 위치 = 앉는 자리, 의자 방향을 보고 책상을 향함)
for (sx, sy, srot), team in zip(SEATS, ["research", "edit", "review", None, "art", "edit", None, "voice"]):
    if team: doll(sx, sy, srot + R(180) if srot == 0 else 0, "sit", TEAM[team])
doll(4.0, 1.6, R(215), "walk", TEAM["research"], held=True)
doll(7.75, 0.75, R(180), "sit", TEAM["pr"], scarf="#f3e2b8")
doll(1.6, 7.2, R(180), "stand", TEAM["review"])

# ── 빛·카메라·렌더 ─────────────────────────────────────────────────────
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (*hexc("#f4efe8"), 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
bpy.ops.object.light_add(type="SUN", rotation=(R(48), R(14), R(-120))); sun = bpy.context.object
sun.data.energy = 3.2; sun.data.angle = R(12); sun.data.color = hexc("#fff3e3")
bpy.ops.object.light_add(type="AREA", location=(-1.5, 4, 2.2), rotation=(0, R(-90), 0)); win = bpy.context.object
win.data.energy = 900; win.data.size = 6; win.data.color = hexc("#e8f2ff")
bpy.ops.object.light_add(type="AREA", location=(6, 2, 6)); fill = bpy.context.object; fill.data.energy = 400; fill.data.size = 8

bpy.ops.object.camera_add(location=(RX / 2 + 11.5, RY / 2 - 11.5, 10.6), rotation=(R(57), 0, R(45)))
cam = bpy.context.object; sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 13.4
cam.data.shift_y = 0.07
cam.data.shift_x = 0.02

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080; sc.render.resolution_percentage = PCT
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.film_transparent = False
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
