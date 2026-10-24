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


import random, mathutils
RND = random.Random(7)

# ── 색(진한 쪽) ───────────────────────────────────────────────────────
C = {
    "floor": "#d6a466", "wall": "#f2ece3", "wall2": "#e7dfd2", "white": "#f6f4f0", "steel": "#7d838c", "dark": "#2b2f35",
    "research": "#4f86c9", "edit": "#3fa37d", "review": "#df6f52", "voice": "#7d5fd0", "art": "#eea733",
    "print": "#7f8c99", "reel": "#21958f", "pr": "#e05c95", "sports": "#28589a",
    "coffee": "#b9784a", "lounge": "#4c9cc4", "game": "#8f5bd1", "plant": "#3f8f45",
}
def m_(name, h, rough=0.6, **kw):
    key = name + h
    if key not in MCACHE: MCACHE[key] = mat(key, hexc(h), rough, **kw)
    return MCACHE[key]
MCACHE = {}
def knitm(h): return m_("knit", h, 0.85, sheen=1.0, knit=(28, 34), ss=0.04)
WOOD = mat("floor", hexc(C["floor"]), 0.5, wood=True)
GLASS = bpy.data.materials.new("glass"); GLASS.use_nodes = True
gb = GLASS.node_tree.nodes["Principled BSDF"]; gb.inputs["Alpha"].default_value = 0.18; gb.inputs["Roughness"].default_value = 0.1
gb.inputs["Base Color"].default_value = (*hexc("#cfe9f7"), 1)   # 얇은 반투명 유리(굴절 없이 — 거울처럼 비치지 않게)

def local(x, y, rot):
    s, c = math.sin(rot), math.cos(rot)
    return lambda dx, dy, z=0: (x + dx * c - dy * s, y + dx * s + dy * c, z)

# ── 방 ───────────────────────────────────────────────────────────────
RX, RY = 17.0, 13.0
box("floor", (RX, RY, 0.12), (RX / 2, RY / 2, -0.06), WOOD, 0.02)
box("wall_back", (RX, 0.16, 3.2), (RX / 2, RY + 0.08, 1.6), m_("w", C["wall"], 0.9), 0.01)
box("wall_left", (0.16, RY, 3.2), (-0.08, RY / 2, 1.6), m_("w2", C["wall2"], 0.9), 0.01)
for i, y in enumerate((1.6, 4.4, 7.2, 10.0)):
    box(f"win{i}", (0.05, 1.8, 1.7), (0.02, y, 1.65), m_("win", "#cfe6f5", 0.1, emit=(hexc("#eaf5fd"), 1.6)), 0.0)
    box(f"sill{i}", (0.12, 1.9, 0.06), (0.06, y, 0.78), m_("wh", C["white"], 0.4), 0.005)

def zone(x0, y0, x1, y1, h, edge=True):
    box("zone", (x1 - x0 - 0.12, y1 - y0 - 0.12, 0.012), ((x0 + x1) / 2, (y0 + y1) / 2, 0.006), m_("rug", h, 0.95, sheen=0.5), 0.03)

def partition(x0, y0, x1, y1, h=1.05, glass=False):
    L = math.hypot(x1 - x0, y1 - y0); a = math.atan2(y1 - y0, x1 - x0)
    if glass:
        box("glass", (L, 0.03, 2.2), ((x0 + x1) / 2, (y0 + y1) / 2, 1.1), GLASS, 0.0, rot=(0, 0, a))
        box("frame", (L, 0.06, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, 2.2), m_("st", C["steel"], 0.4, metal=0.5), 0.005, rot=(0, 0, a))
        box("frameb", (L, 0.06, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03), m_("st", C["steel"], 0.4, metal=0.5), 0.005, rot=(0, 0, a))
    else:
        box("part", (L, 0.08, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), m_("pt", "#f7f4ee", 0.8), 0.02, rot=(0, 0, a))

# ── 가구 ─────────────────────────────────────────────────────────────
WH = m_("wh", C["white"], 0.35); ST = m_("st", C["steel"], 0.4, metal=0.5); DK = m_("dk", C["dark"], 0.3)
def screen(h="#9ccbe6"): return m_("scr", h, 0.2, emit=(hexc(h), 0.9))
def desk(x, y, rot, top=None, monitors=1, scr="#9ccbe6"):
    P = local(x, y, rot)
    box("desk", (1.3, 0.7, 0.045), P(0, 0, 0.72), m_("dt", top, 0.45) if top else WH, 0.008, rot=(0, 0, rot))
    for dx in (-0.6, 0.6):
        box("leg", (0.05, 0.62, 0.03), P(dx, 0, 0.03), ST, 0.005, rot=(0, 0, rot)); box("leg", (0.05, 0.05, 0.7), P(dx, 0, 0.36), ST, 0.005, rot=(0, 0, rot))
    for k in range(monitors):
        dx = (k - (monitors - 1) / 2) * 0.5
        box("mon", (0.46, 0.03, 0.3), P(dx, 0.2, 1.0), screen(scr), 0.008, rot=(0, 0, rot + (k - (monitors - 1) / 2) * -0.25))
        box("monb", (0.48, 0.02, 0.32), P(dx, 0.225, 1.0), DK, 0.008, rot=(0, 0, rot + (k - (monitors - 1) / 2) * -0.25))
        box("mons", (0.04, 0.04, 0.14), P(dx, 0.25, 0.8), DK, 0.004, rot=(0, 0, rot))
    box("kb", (0.38, 0.12, 0.015), P(0, -0.08, 0.75), WH, 0.003, rot=(0, 0, rot))
    box("mug", (0.07, 0.07, 0.09), P(-0.5, 0.0, 0.785), m_("mug", RND.choice(["#df6f52", "#4f86c9", "#eea733", "#3fa37d"]), 0.5), 0.012, rot=(0, 0, rot))
    if RND.random() < 0.5: box("paper", (0.22, 0.3, 0.02), P(0.45, -0.05, 0.755), m_("pp", "#fbf8f1", 0.7), 0.002, rot=(0, 0, rot + 0.3))

def chair(x, y, rot, h="#3b3f46"):
    P = local(x, y, rot); cm = m_("ch", h, 0.8, sheen=0.4)
    box("seat", (0.46, 0.44, 0.08), P(0, 0, 0.46), cm, 0.03, rot=(0, 0, rot))
    box("back", (0.44, 0.07, 0.5), P(0, -0.22, 0.79), cm, 0.03, rot=(R(-8), 0, rot))
    cyl("gas", 0.025, 0.36, P(0, 0, 0.24), ST)
    for k in range(5):
        a = rot + k * 2 * math.pi / 5
        box("spoke", (0.3, 0.04, 0.03), (x + 0.15 * math.cos(a), y + 0.15 * math.sin(a), 0.06), DK, 0.008, rot=(0, 0, a))

def plant(x, y, big=True):
    h = 0.45 if big else 0.24
    cyl("pot", 0.22 if big else 0.13, h, (x, y, h / 2), m_("pot", RND.choice(["#c9714a", "#e9e2d6", "#2b2f35"]), 0.6))
    for k in range(10 if big else 5):
        a = RND.uniform(0, 6.28); r_ = RND.uniform(0.05, 0.26 if big else 0.12); z = h + RND.uniform(0.25, 1.0 if big else 0.35)
        o = sph("leaf", RND.uniform(0.13, 0.21) if big else 0.09, (x + r_ * math.cos(a), y + r_ * math.sin(a), z), m_("lf", C["plant"], 0.5, ss=0.1), scale=(1.4, 0.45, 0.9))
        o.rotation_euler = (RND.uniform(-0.4, 0.4), RND.uniform(-0.4, 0.4), a)

def board(x, y, rot, w=1.6, kind="white", accent="#df6f52"):
    P = local(x, y, rot)
    base = WH if kind == "white" else m_("cork", "#b98a5a", 0.9)
    box("board", (w, 0.04, 1.0), P(0, 0, 1.55), base, 0.01, rot=(0, 0, rot))
    box("bframe", (w + 0.06, 0.03, 1.06), P(0, 0.02, 1.55), ST, 0.01, rot=(0, 0, rot))
    for k in range(int(w * 3)):
        if kind == "white":
            box("mark", (RND.uniform(0.15, 0.45), 0.01, 0.025), P(-w / 2 + 0.2 + (k % 3) * w / 3.2, -0.03, 1.85 - (k // 3) * 0.16), m_("mk", RND.choice([accent, "#2b2f35", "#4f86c9"]), 0.6), 0.0, rot=(0, 0, rot))
        else:
            box("note", (0.22, 0.01, 0.18), P(-w / 2 + 0.25 + (k % 4) * w / 4.4, -0.03, 1.85 - (k // 4) * 0.28), m_("nt", RND.choice(["#f7d84a", "#7fc8e8", "#f49ab8", "#9fd88b"]), 0.8), 0.0, rot=(0, 0, rot + RND.uniform(-.1, .1)))

def shelf(x, y, rot, w=1.4, h=1.8, books=True):
    P = local(x, y, rot)
    box("shelf", (w, 0.36, h), P(0, 0, h / 2), m_("sh", "#c9935e", 0.5), 0.01, rot=(0, 0, rot))
    for r_ in range(4):
        z = 0.2 + r_ * (h - 0.2) / 4
        bx = -w / 2 + 0.1
        while bx < w / 2 - 0.12 and books:
            bw = RND.uniform(0.05, 0.1)
            box("book", (bw, 0.26, RND.uniform(0.22, 0.32)), P(bx + bw / 2, -0.06, z + 0.14), m_("bk", RND.choice(["#4f86c9", "#df6f52", "#eea733", "#3fa37d", "#7d5fd0", "#f2ece3", "#2b2f35"]), 0.6), 0.004, rot=(0, 0, rot))
            bx += bw + 0.01

def booth(x, y):
    for (a, b, c, d) in ((x - .8, y - .8, x + .8, y - .8), (x + .8, y - .8, x + .8, y + .8), (x - .8, y + .8, x + .8, y + .8), (x - .8, y - .8, x - .8, y + .8)):
        partition(a, b, c, d, glass=True)
    box("roof", (1.7, 1.7, 0.06), (x, y, 2.23), WH, 0.01)
    box("foam", (1.5, 0.06, 1.4), (x, y + 0.74, 1.2), m_("foam", "#4b3d7a", 0.95), 0.02)
    cyl("micst", 0.015, 1.3, (x + 0.25, y + 0.2, 0.65), DK); sph("mic", 0.06, (x + 0.25, y + 0.05, 1.32), DK, scale=(1, 1, 1.4))
    cyl("pop", 0.1, 0.01, (x + 0.25, y - 0.05, 1.32), DK, rot=(R(90), 0, 0))

def easel(x, y, rot, h):
    P = local(x, y, rot)
    for dx in (-0.25, 0.25): box("el", (0.04, 0.04, 1.7), P(dx, 0, 0.85), m_("ew", "#b9784a", 0.6), 0.005, rot=(R(-8), 0, rot))
    box("canvas", (0.8, 0.04, 0.65), P(0, -0.1, 1.2), m_("cv", "#fbf8f1", 0.8), 0.005, rot=(R(-8), 0, rot))
    box("paint", (0.6, 0.02, 0.45), P(0, -0.13, 1.2), m_("pa", h, 0.6), 0.005, rot=(R(-8), 0, rot))

def copier(x, y, rot):
    P = local(x, y, rot)
    box("cp", (0.9, 0.7, 1.0), P(0, 0, 0.5), m_("cp", "#e4e1db", 0.5), 0.03, rot=(0, 0, rot))
    box("cplid", (0.8, 0.6, 0.06), P(0, 0, 1.03), DK, 0.02, rot=(0, 0, rot))
    box("tray", (0.5, 0.35, 0.03), P(0.55, 0, 0.75), WH, 0.01, rot=(0, 0, rot))
    box("panel", (0.25, 0.12, 0.05), P(-0.25, -0.3, 1.04), screen("#7fd0c8"), 0.01, rot=(0, 0, rot))
    for k in range(3): box("stack", (0.32, 0.24, 0.12 + 0.04 * k), P(-0.2 + k * 0.38, -0.75, 0.06 + 0.02 * k), m_("pp", "#fbf8f1", 0.7), 0.004, rot=(0, 0, rot + RND.uniform(-.2, .2)))

def ringlight(x, y):
    for k in range(3):
        a = k * 2.1
        box("tri", (0.03, 0.03, 1.5), (x + 0.18 * math.cos(a), y + 0.18 * math.sin(a), 0.72), DK, 0.004, rot=(0.18 * math.sin(a), -0.18 * math.cos(a), 0))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.32, minor_radius=0.04, location=(x, y, 1.65), rotation=(R(90), 0, R(-45)))
    o = bpy.context.object; o.data.materials.append(m_("ring", "#ffffff", 0.2, emit=(hexc("#fff6e8"), 6))); bpy.ops.object.shade_smooth()
    box("phone", (0.08, 0.01, 0.16), (x, y, 1.65), DK, 0.01, rot=(0, 0, R(-45)))

def sofa(x, y, rot, h, w=2.0):
    P = local(x, y, rot); sm = m_("sofa", h, 0.9, sheen=0.7)
    box("sbase", (w, 0.85, 0.42), P(0, 0, 0.21), sm, 0.08, rot=(0, 0, rot))
    box("sback", (w, 0.25, 0.8), P(0, 0.33, 0.5), sm, 0.1, rot=(0, 0, rot))
    for s_ in (-1, 1): box("sarm", (0.22, 0.85, 0.62), P(s_ * (w / 2 + 0.05), 0, 0.31), sm, 0.08, rot=(0, 0, rot))
    for k in range(2): box("cush", (w / 2 - 0.06, 0.66, 0.14), P(-w / 4 + k * w / 2, -0.06, 0.48), sm, 0.06, rot=(0, 0, rot))
    box("pillow", (0.38, 0.12, 0.34), P(w / 2 - 0.3, 0.18, 0.7), m_("pil", "#f7d84a", 0.9, sheen=0.6), 0.06, rot=(R(-15), 0, rot))

def beanbag(x, y, h):
    sph("bean", 0.42, (x, y, 0.26), m_("bean", h, 0.9, sheen=0.8), scale=(1.1, 1.1, 0.62))

def stool(x, y, h):
    cyl("stseat", 0.2, 0.06, (x, y, 0.76), m_("sto", h, 0.6)); cyl("stleg", 0.03, 0.72, (x, y, 0.38), ST); cyl("stb", 0.18, 0.02, (x, y, 0.01), ST)

# ── 니트 인형 (생김새 변수) ──────────────────────────────────────────
def doll(x, y, rot, pose="sit", body="#e8dccb", hat="beanie", hatc="#4f86c9", scarf=None, glasses=False, phones=False,
         stripes=None, size=1.0, held=None, seat=0.5, face=True):
    """pose: sit(책상) · sofa · bean · stand · walk · cheer · drink · stool. held: papers·mug·laptop·phone·pad."""
    DS = 1.35 * size; before = set(bpy.data.objects)
    km = knitm(body); hm = knitm(hatc); P = local(x, y, rot)
    seated = pose in ("sit", "sofa", "bean", "stool")
    hip = (seat / DS) if seated else 0.42
    lean = -0.06 if pose in ("sofa", "bean") else 0.0
    sph("body", 0.17, P(0, lean, hip + 0.16), km, scale=(1.0, 0.85, 1.15))
    if stripes:
        for k in range(2): cyl("stripe", 0.172, 0.04, P(0, lean, hip + 0.1 + k * 0.1), knitm(stripes))
    hz = hip + 0.47
    sph("head", 0.19, P(0, lean, hz), km, scale=(1.05, 1.0, 0.95))
    if hat in ("beanie", "pom"):
        sph("hat", 0.197, P(0, lean - 0.01, hz + 0.06), hm, scale=(1.06, 1.04, 0.82)); cyl("band", 0.203, 0.07, P(0, lean, hz + 0.03), hm)
        if hat == "pom": sph("pom", 0.065, P(0, lean - 0.01, hz + 0.25), hm)
    elif hat == "beret":
        sph("beret", 0.22, P(0.04, lean - 0.02, hz + 0.15), hm, scale=(1.05, 1.05, 0.38)); sph("stem", 0.02, P(0.04, lean - 0.02, hz + 0.24), hm)
    elif hat == "cap":
        sph("cap", 0.196, P(0, lean - 0.01, hz + 0.05), hm, scale=(1.05, 1.04, 0.8)); box("brim", (0.24, 0.18, 0.025), P(0, lean + 0.2, hz + 0.08), hm, 0.02, rot=(0, 0, rot))
    elif hat == "ears":
        sph("hat", 0.197, P(0, lean - 0.01, hz + 0.06), hm, scale=(1.06, 1.04, 0.82))
        for s_ in (-1, 1): sph("ear", 0.07, P(s_ * 0.13, lean - 0.02, hz + 0.22), hm, scale=(0.8, 0.5, 1.2))
    else:   # 털실 머리
        for k in range(7):
            a = k / 7 * math.pi; sph("hair", 0.08, P(math.cos(a) * 0.15, lean - 0.05 + math.sin(a) * 0.02, hz + 0.12 + math.sin(a) * 0.05), knitm(hatc))
    if phones:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.2, minor_radius=0.02, location=P(0, lean, hz + 0.02), rotation=(0, R(90), rot)); o = bpy.context.object; o.data.materials.append(DK)
        for s_ in (-1, 1): sph("cup", 0.06, P(s_ * 0.2, lean, hz - 0.02), DK, scale=(0.6, 1, 1))
    if scarf:
        cyl("scarf", 0.15, 0.07, P(0, lean, hip + 0.31), knitm(scarf)); box("tail", (0.07, 0.03, 0.18), P(0.06, lean + 0.14, hip + 0.22), knitm(scarf), 0.02, rot=(0, 0, rot))
    if face:
        for e in (-0.065, 0.065):
            sph("eye", 0.024, P(e, lean + 0.172, hz - 0.01), m_("eye", "#151515", 0.2))
            sph("cheek", 0.03, P(e * 1.65, lean + 0.158, hz - 0.06), m_("chk", "#ef8d86", 0.9, sheen=0.4), scale=(1, 0.4, 0.7))
        if glasses:
            for e in (-0.065, 0.065):
                bpy.ops.mesh.primitive_torus_add(major_radius=0.045, minor_radius=0.008, location=P(e, lean + 0.185, hz - 0.01), rotation=(R(90), 0, rot)); o = bpy.context.object; o.data.materials.append(DK)
    # 팔·다리
    A = lambda dx, dy, dz: P(dx, dy, dz)
    if seated:
        legz = hip + 0.03; foot = 0.12 if pose in ("sit", "stool") else hip * 0.5
        reach = 0.3 if pose == "sit" else 0.18
        for s_ in (-1, 1):
            capsule("thigh", 0.065, 0, A(s_ * 0.08, lean, legz), A(s_ * 0.08, 0.26, legz), km)
            if pose == "stool": capsule("shin", 0.06, 0, A(s_ * 0.08, 0.27, legz), A(s_ * 0.08, 0.3, legz - 0.3), km)
            else: capsule("shin", 0.06, 0, A(s_ * 0.08, 0.28, legz - 0.01), A(s_ * 0.08, 0.32 if pose == "sit" else 0.4, foot), km)
            if pose == "sit" or held in ("pad", "laptop"):
                capsule("arm", 0.05, 0, A(s_ * 0.17, lean, hip + 0.27), A(s_ * 0.12, reach, hip + 0.24), km)
            elif held == "mug" and s_ == 1:
                capsule("arm", 0.05, 0, A(0.17, lean, hip + 0.27), A(0.08, 0.16, hip + 0.33), km)
            else:
                capsule("arm", 0.05, 0, A(s_ * 0.17, lean, hip + 0.27), A(s_ * 0.2, lean + 0.05, hip + 0.06), km)
    else:
        swing = 0.12 if pose == "walk" else 0.0
        for s_ in (-1, 1):
            capsule("leg", 0.065, 0, A(s_ * 0.08, 0, hip), A(s_ * 0.08, s_ * swing, 0.06), km)
            if pose == "cheer":
                capsule("arm", 0.05, 0, A(s_ * 0.17, 0, hip + 0.29), A(s_ * 0.26, 0.02, hip + 0.6), km)
            elif held in ("papers", "pad", "laptop"):
                capsule("arm", 0.05, 0, A(s_ * 0.17, 0, hip + 0.27), A(s_ * 0.12, 0.2, hip + 0.22), km)
            elif held in ("mug", "phone") and s_ == 1:
                capsule("arm", 0.05, 0, A(0.17, 0, hip + 0.27), A(0.1, 0.14, hip + (0.47 if held == "phone" else 0.32)), km)
            else:
                capsule("arm", 0.05, 0, A(s_ * 0.17, 0, hip + 0.27), A(s_ * 0.2, -s_ * swing, hip + 0.05), km)
    if held == "papers": box("papers", (0.26, 0.2, 0.08), A(0, 0.24, hip + 0.24), m_("pp", "#fbf8f1", 0.7), 0.005, rot=(0, 0, rot))
    if held == "mug": box("hmug", (0.07, 0.07, 0.09), A(0.06, 0.2, hip + 0.33), m_("mug", "#df6f52", 0.5), 0.012, rot=(0, 0, rot))
    if held == "phone": box("hphone", (0.04, 0.02, 0.09), A(0.12, 0.13, hip + 0.47), DK, 0.008, rot=(0, 0, rot))
    if held == "pad": box("pad", (0.3, 0.22, 0.02), A(0, 0.28, hip + 0.22), DK, 0.01, rot=(R(-30), 0, rot))
    if held == "laptop":
        box("lap", (0.34, 0.24, 0.02), A(0, 0.3, hip + 0.2), m_("lap", "#c4c8ce", 0.3, metal=0.6), 0.01, rot=(0, 0, rot))
        box("lscr", (0.34, 0.02, 0.22), A(0, 0.42, hip + 0.31), screen("#9ccbe6"), 0.01, rot=(R(-15), 0, rot))
    for o in set(bpy.data.objects) - before:
        o.location = (x + (o.location.x - x) * DS, y + (o.location.y - y) * DS, o.location.z * DS)
        o.scale = tuple(v * DS for v in o.scale)

# 인형 생김새 무작위 변수(부서 색은 모자에, 몸통·소품은 사람마다)
BODIES = ["#e8dccb", "#f2c14e", "#7aa7dd", "#ee8b6e", "#6cc39d", "#a888e0", "#f39ac0", "#8a6a52", "#46566a", "#f4f1ea"]
HATS = ["beanie", "pom", "beret", "cap", "ears", "hair"]
def person(x, y, rot, team, pose="sit", **kw):
    v = dict(body=RND.choice(BODIES), hat=RND.choice(HATS), hatc=C[team] if team in C else team,
             scarf=RND.choice([None, None, "#f7d84a", "#ffffff", "#df6f52", "#2b2f35"]), glasses=RND.random() < 0.3,
             stripes=RND.choice([None, None, "#ffffff", "#2b2f35"]), size=RND.uniform(0.92, 1.08))
    if v["hat"] == "hair": v["hatc"] = RND.choice(["#5a3b2a", "#2b2f35", "#c98b5b", "#e7c26b"])
    v.update(kw); doll(x, y, rot, pose, **v)

# ── 배치 ─────────────────────────────────────────────────────────────
# 뒷줄(y 8.6~13): 취재 · 편집·디자인 · 검수   / 가운데 줄(y 4.6~8): 녹음 · 화실 · 인쇄 · 릴스 · 홍보   / 앞줄(y 0~4): 커피바 · 라운지 · 오락 · 스포츠국(유리방)
zone(0, 8.8, 5.4, 13, "#a9c6ea"); zone(5.6, 8.8, 11.4, 13, "#9fd6bd"); zone(11.6, 8.8, 17, 13, "#f3b3a1")
zone(0, 4.6, 2.6, 8.2, "#c4b5ef"); zone(2.8, 4.6, 6.0, 8.2, "#f6d48f"); zone(6.2, 4.6, 9.2, 8.2, "#c9d0d8"); zone(9.4, 4.6, 12.6, 8.2, "#94d3cf"); zone(12.8, 4.6, 17, 8.2, "#f4b3cf")
zone(0, 0, 3.8, 4.0, "#e3c2a5"); zone(4.0, 0, 8.4, 4.0, "#a7d3ea"); zone(8.6, 0, 12.4, 4.0, "#cdb6ee"); zone(12.8, 0, 17, 4.0, "#9fb7dc")
# 낮은 칸막이(통로는 비워 둔다)
partition(5.5, 9.4, 5.5, 13); partition(11.5, 9.4, 11.5, 13); partition(0.0, 8.5, 3.6, 8.5); partition(13.4, 8.5, 17, 8.5)
partition(6.1, 4.8, 6.1, 7.4, 0.9); partition(9.3, 4.8, 9.3, 7.4, 0.9); partition(12.7, 4.8, 12.7, 7.4, 0.9)
partition(12.7, 0.1, 12.7, 3.0, glass=True); partition(12.7, 4.1, 17, 4.1, glass=True)

# 취재팀: 책장 벽 + 책상 4 + 코르크판
shelf(0.3, 11.0, R(-90), 2.4); shelf(0.3, 9.4, R(-90), 1.2, books=True)
board(2.8, 12.92, 0, 1.6, "cork")
for k, dx in enumerate((1.9, 3.7)):
    desk(dx, 11.0, 0, monitors=1); chair(dx, 10.25, 0, "#4f86c9")
    desk(dx, 9.55 + 0.0, 0, monitors=1, scr="#bfe0f2") if False else None
person(1.9, 10.25, 0, "research", "sit"); person(3.7, 10.25, 0, "research", "sit", held=None)
person(1.2, 9.4, R(160), "research", "stand", held="papers")
# 편집·디자인팀: 마주 보는 책상 섬(듀얼 모니터, 모니터끼리 등을 맞댐) + 화이트보드
for k, dx in enumerate((6.9, 8.5, 10.1)):
    desk(dx, 10.45, 0, monitors=2); chair(dx, 9.7, 0, "#3fa37d")
    desk(dx, 11.25, R(180), monitors=2); chair(dx, 12.0, R(180), "#3fa37d")
board(8.5, 12.92, 0, 2.6, "white", C["edit"])
person(6.9, 9.7, 0, "edit"); person(10.1, 9.7, 0, "edit"); person(8.5, 12.0, R(180), "edit"); person(10.1, 12.0, R(180), "edit")
# 검수팀: 회의 탁자 + 도장 + 체크리스트 보드
box("mtable", (2.4, 1.1, 0.05), (14.3, 10.8, 0.74), m_("mt", "#f6f4f0", 0.4), 0.02); cyl("mtl", 0.06, 0.72, (13.5, 10.8, 0.37), ST); cyl("mtl", 0.06, 0.72, (15.1, 10.8, 0.37), ST)
for dx in (13.6, 15.0):
    chair(dx, 10.0, 0, "#df6f52"); chair(dx, 11.6, R(180), "#df6f52")
cyl("stamp", 0.09, 0.08, (14.3, 10.8, 0.81), m_("stp", "#c0392b", 0.5)); cyl("stamph", 0.03, 0.14, (14.3, 10.8, 0.92), m_("sth", "#6b4a35", 0.5)); sph("stampk", 0.06, (14.3, 10.8, 1.02), m_("sth", "#6b4a35", 0.5))
for k in range(4): box("doc", (0.3, 0.4, 0.01), (13.5 + k * 0.5, 10.75 + RND.uniform(-.2, .2), 0.77), m_("pp", "#fbf8f1", 0.7), 0.002, rot=(0, 0, RND.uniform(-.4, .4)))
board(14.3, 12.92, 0, 2.2, "white", "#c0392b"); shelf(16.7, 11.2, R(90), 1.6)
person(13.6, 10.0, 0, "review", "sit", held=None); person(15.0, 11.6, R(180), "review", "sit")
# 녹음실: 유리 부스
booth(1.3, 6.4); person(1.15, 6.1, R(15), "voice", "sit", phones=True, seat=0.5)
chair(1.15, 6.1, R(15), "#7d5fd0")
# 화실: 이젤 3 + 그림 탁자
easel(3.5, 7.4, R(200), "#e05c95"); easel(4.6, 7.6, R(180), "#4f86c9"); easel(5.5, 6.9, R(160), "#eea733")
box("dtable", (1.2, 0.8, 0.05), (4.3, 5.4, 0.74), m_("dt", "#e9d2b0", 0.5), 0.01); cyl("dtl", 0.05, 0.72, (4.3, 5.4, 0.37), ST)
person(4.6, 6.8, R(180), "art", "stand", held="pad", hat="beret")
# 인쇄실: 복합기 + 종이 선반
copier(7.6, 7.5, R(180)); shelf(8.9, 7.7, R(180), 0.9, 1.4)
person(7.2, 6.2, R(200), "print", "walk", held="papers")
# 릴스 편집실: 어두운 편집석 + 모니터 3
box("rdesk", (2.2, 0.8, 0.05), (11.0, 7.3, 0.74), DK, 0.01); cyl("rdl", 0.05, 0.72, (10.1, 7.3, 0.37), ST); cyl("rdl", 0.05, 0.72, (11.9, 7.3, 0.37), ST)
for k in range(3): box("rmon", (0.6, 0.03, 0.36), (10.35 + k * 0.65, 7.55, 1.05), screen(["#f49ab8", "#7fd0c8", "#f7d84a"][k]), 0.01, rot=(0, 0, (k - 1) * -0.2))
chair(11.0, 6.55, 0, "#21958f"); person(11.0, 6.55, 0, "reel", "sit", phones=True)
# 홍보팀: 링라이트 + 촬영 탁자 + 휴대폰 거치대
ringlight(14.0, 6.0); box("ptable", (1.2, 0.7, 0.05), (15.6, 7.3, 0.74), WH, 0.01); cyl("ptl", 0.05, 0.72, (15.6, 7.3, 0.37), ST)
for k in range(3): box("prod", (0.14, 0.14, 0.22), (15.2 + k * 0.35, 7.3, 0.88), m_("prd", ["#e05c95", "#f7d84a", "#7fd0c8"][k], 0.5), 0.02)
person(14.7, 6.6, R(225), "pr", "stand", held="phone"); board(15.6, 8.12, R(180), 1.4, "cork")
# 커피바: 카운터 + 머신 + 의자
box("counter", (3.0, 0.7, 1.0), (1.9, 0.5, 0.5), m_("ctr", "#8a5a3c", 0.5), 0.02); box("ctop", (3.1, 0.8, 0.05), (1.9, 0.5, 1.02), WH, 0.01)
box("cm", (0.45, 0.4, 0.5), (1.0, 0.5, 1.3), m_("cmm", "#c0392b", 0.3, metal=0.3), 0.04); box("cm2", (0.3, 0.3, 0.35), (1.6, 0.5, 1.22), ST, 0.03)
for k in range(4): box("cup", (0.08, 0.08, 0.1), (2.2 + k * 0.18, 0.4, 1.1), m_("mug", ["#df6f52", "#4f86c9", "#eea733", "#3fa37d"][k], 0.5), 0.012)
for k, xx in enumerate((1.0, 1.9, 2.8)): stool(xx, 1.25, ["#eea733", "#21958f", "#df6f52"][k])
box("cshelf", (2.4, 0.25, 0.04), (1.9, 0.02, 1.8), m_("sh", "#c9935e", 0.5), 0.01)
person(1.9, 1.25, R(180), "#b9784a", "stool", held="mug", seat=0.79); person(3.2, 2.4, R(150), "#b9784a", "stand", held="mug")
plant(0.4, 3.5)
# 소파 라운지
sofa(6.2, 1.0, R(180), "#3f86b8"); sofa(4.6, 2.5, R(90), "#e98f6a", 1.6)
box("rugl", (3.0, 2.2, 0.015), (6.2, 2.3, 0.02), m_("rugl", "#f3e9d8", 0.95, sheen=0.6), 0.03)
cyl("ctab", 0.45, 0.05, (6.3, 2.4, 0.42), m_("ct", "#c9935e", 0.5)); cyl("ctl", 0.05, 0.4, (6.3, 2.4, 0.2), ST)
person(5.8, 0.9, R(180), "#3f86b8", "sofa", held="mug", seat=0.52); person(6.7, 0.9, R(180), "#3f86b8", "sofa", held="pad", seat=0.52)
plant(8.0, 3.6); plant(4.4, 0.4, False)
# 오락 코너: 큰 TV(방 안쪽 벽 쪽, 카메라를 향함) + 빈백 + 테이블 축구
box("tvst", (1.8, 0.45, 0.5), (10.5, 3.65, 0.25), m_("tvs", "#2b2f35", 0.5), 0.02); box("tvb", (1.74, 0.05, 0.99), (10.5, 3.72, 1.05), DK, 0.02); box("tv", (1.7, 0.04, 0.95), (10.5, 3.68, 1.05), screen("#6fb7ff"), 0.02)
beanbag(10.0, 2.0, "#eea733"); beanbag(11.1, 1.9, "#e05c95")
person(10.0, 2.0, R(0), "#8f5bd1", "bean", held="pad", seat=0.42); person(11.1, 1.9, R(-10), "#8f5bd1", "bean", held="pad", seat=0.42)
box("fb", (1.3, 0.75, 0.25), (9.5, 0.8, 0.85), m_("fbt", "#3fa37d", 0.5), 0.03); box("fbl", (1.4, 0.85, 0.08), (9.5, 0.8, 0.98), m_("fbw", "#c9935e", 0.5), 0.02)
for k in range(4): cyl("rod", 0.015, 1.1, (9.0 + k * 0.33, 0.8, 0.98), ST, rot=(R(90), 0, 0))
for dx in (-0.55, 0.55): box("fbleg", (0.08, 0.08, 0.72), (9.5 + dx, 0.8, 0.36), DK, 0.01)
person(11.6, 0.9, R(200), "#8f5bd1", "cheer")
# 스포츠국(유리방): 큰 화면은 안쪽 유리벽에서 카메라를 향함 + 책상 + 응원 머플러
box("sscrf", (2.5, 0.05, 1.4), (14.9, 3.92, 1.5), DK, 0.02); box("sscr", (2.4, 0.04, 1.3), (14.9, 3.88, 1.5), screen("#38c172"), 0.02)
for k, dx in enumerate((14.0, 15.8)):
    desk(dx, 2.3, 0, monitors=2, scr="#38c172"); chair(dx, 1.55, 0, "#28589a")
person(14.0, 1.55, 0, "sports", "sit", hat="cap"); person(15.6, 0.7, R(200), "sports", "cheer", hat="cap")
box("scarfw", (1.4, 0.03, 0.18), (14.9, 3.86, 2.35), knitm("#28589a"), 0.02)
plant(16.6, 3.4)
# 통로의 걷는 인형
person(6.0, 4.3, R(-60), "research", "walk", held="papers")
plant(16.6, 12.5); plant(5.4, 8.4, False); plant(11.6, 8.4, False)

# ── 빛·카메라·렌더 ─────────────────────────────────────────────────────
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (*hexc("#efe7dc"), 1); world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
bpy.ops.object.light_add(type="SUN", rotation=(R(46), R(12), R(-118))); sun = bpy.context.object; sun.data.energy = 3.4; sun.data.angle = R(10); sun.data.color = hexc("#fff0dc")
bpy.ops.object.light_add(type="AREA", location=(-2, RY / 2, 2.4), rotation=(0, R(-90), 0)); w_ = bpy.context.object; w_.data.energy = 1800; w_.data.size = 12; w_.data.color = hexc("#e6f1ff")
bpy.ops.object.light_add(type="AREA", location=(RX / 2, RY / 2, 7)); f_ = bpy.context.object; f_.data.energy = 900; f_.data.size = 14
bpy.ops.object.camera_add(location=(RX / 2 + 16, RY / 2 - 16, 15), rotation=(R(57), 0, R(45)))
cam = bpy.context.object; sc.camera = cam; cam.data.type = "ORTHO"; cam.data.ortho_scale = 22.0; cam.data.shift_y = -0.01; cam.data.shift_x = 0.02
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6; sc.cycles.transmission_bounces = 6
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080; sc.render.resolution_percentage = PCT
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
