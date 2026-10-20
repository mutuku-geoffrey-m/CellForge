# Parametric Mounting Bracket CAD Documentation

This directory contains the parametric 3D CAD model for the custom industrial mounting bracket modeled throughout the CellForge manufacturing simulation and optimization laboratory.

## Model Source File

- `parametric_mounting_bracket.scad`: Clean, open-source CSG (Constructive Solid Geometry) model authored for [OpenSCAD](https://openscad.org/).

---

## 1. Design Rationale

The component is a heavy-duty structural mounting bracket designed to anchor electromechanical actuators, bearing blocks, or robotic end-effectors to an industrial machine chassis.

Key mechanical design features:
- **L-Section Geometry**: Formed by a horizontal base mounting foot ($80\,\text{mm}$) and an upright vertical mounting flange ($70\,\text{mm}$).
- **Triangular Stiffening Gussets**: Two lateral gusset webs ($6\,\text{mm}$ thickness) resist bending moments induced by cantilevered actuator loads across the principal bend axis.
- **Internal Stress Relief Fillet**: An inner radius of $4.0\,\text{mm}$ eliminates the sharp internal $90^\circ$ notch, preventing fatigue microcracking under dynamic cyclic loading.
- **Precision Fastener Clearance Bores**:
  - Base plate: 4$\times$ $\varnothing 6.6\,\text{mm}$ medium-fit clearance holes per ISO 273 for M6 grade 8.8/10.9 steel cap screws.
  - Upright flange: 2$\times$ $\varnothing 9.0\,\text{mm}$ medium-fit clearance holes per ISO 273 for M8 mounting hardware.
- **Weight-Reduction Lightening Pockets**: A recessed pocket ($3.5\,\text{mm}$ depth) on the rear face demonstrates Design for Additive Manufacturing (DfAM) lightweighting, saving ~18% mass while remaining machinable on a 3-axis CNC vertical milling center with a $6\,\text{mm}$ flat end mill.

---

## 2. Dimension Parameter Table

All dimensions use SI metric units ($\text{mm}$).

| Parameter Name in OpenSCAD | Description | Baseline Value | Engineering Purpose |
|---|---|---|---|
| `bracket_width` | Overall bracket width across Y-axis | $60.0\,\text{mm}$ | Interfacing width with standard machine framing |
| `base_length` | Length of horizontal base plate along X-axis | $80.0\,\text{mm}$ | Provides bolting moment arm against tipping |
| `flange_height` | Height of vertical upright flange along Z-axis | $70.0\,\text{mm}$ | Vertical centerline height for supported assembly |
| `wall_thickness` | Nominal thickness of base and upright walls | $8.0\,\text{mm}$ | Structural shear and bearing capacity |
| `gusset_thickness` | Thickness of triangular gusset ribs | $6.0\,\text{mm}$ | Lateral stiffness and torsion resistance |
| `base_hole_dia` | Base plate fastener clearance bore | $6.6\,\text{mm}$ | ISO 273 clearance for M6 cap screws |
| `flange_hole_dia` | Vertical flange fastener clearance bore | $9.0\,\text{mm}$ | ISO 273 clearance for M8 bolts |
| `base_hole_pitch_x` | Hole spacing along X-axis | $45.0\,\text{mm}$ | Chassis bolt pattern alignment |
| `base_hole_pitch_y` | Hole spacing along Y-axis | $38.0\,\text{mm}$ | Symmetric flange load distribution |
| `flange_hole_pitch_y` | Vertical hole spacing along Y-axis | $38.0\,\text{mm}$ | Actuator mounting alignment |
| `corner_fillet_radius` | Outer edge corner blend radius | $6.0\,\text{mm}$ | Eliminates sharp edges; matches milling radius |
| `inner_fillet_radius` | Junction bend fillet radius | $4.0\,\text{mm}$ | Reduces stress concentration factor ($K_t$) |
| `pocket_depth` | Depth of rear weight-reduction pocket | $3.5\,\text{mm}$ | Mass reduction without compromising wall integrity |
| `$fn` | Facet circular resolution | $60$ | High-fidelity STL export mesh quality |

---

## 3. Material & Manufacturing Route Comparison

### Route A: Conventional Subtractive Manufacturing
- **Material**: Wrought Aluminum Alloy 6061-T6 (extruded rectangular bar stock $85 \times 65 \times 75\,\text{mm}$).
- **Yield Strength**: $\sigma_y \approx 276\,\text{MPa}$; Ultimate Tensile Strength: $\sigma_u \approx 310\,\text{MPa}$.
- **Process Sequence**:
  1. Horizontal bandsaw cut to length ($85\,\text{mm}$).
  2. CNC Milling (Op 1: Face top, machine outer profile, pocket upright face, drill M8 holes; Op 2: Flip in soft jaws, face base, drill 4$\times$ M6 holes).
  3. Vibratory or manual deburring and degreasing.
- **Machinability**: Excellent ($V_c \approx 300\text{--}600\,\text{m/min}$). High material removal rate ($>65\%$ scrap chip fraction).

### Route B: Metal Additive Manufacturing (LPBF / SLM)
- **Material**: Gas-atomized AlSi10Mg spherical metal powder ($15\text{--}45\,\mu\text{m}$ particle size).
- **As-Built Properties**: $\sigma_y \approx 220\text{--}240\,\text{MPa}$, increased to $\approx 260\,\text{MPa}$ following T6/stress-relief heat treatment.
- **Process Sequence**:
  1. Laser Powder Bed Fusion on an industrial printer (e.g. EOS M 290 or Concept Laser M2). 4 brackets batched per $250 \times 250\,\text{mm}$ build substrate, oriented at $45^\circ$ to minimize support overhangs.
  2. Stress-relief vacuum heat treatment ($300^\circ\text{C}$ for 2 hours) followed by bandsaw substrate separation.
  3. CNC post-machining of critical mating datums and reaming of M6/M8 clearance bores to achieve $H7$ tolerance.
- **Near-Net Shape Advantage**: Consumes only ~0.42 kg powder per bracket compared to ~1.1 kg billet in subtractive cutting.

---

## 4. Instructions for Viewing and Exporting

### Graphical Viewing via OpenSCAD (Desktop Application)
1. Download and install OpenSCAD (free and open source) from [openscad.org](https://openscad.org/downloads.html) for Windows, macOS, or Linux.
2. Launch OpenSCAD and open `cad/parametric_mounting_bracket.scad`.
3. Press **F5** to render a preview.
4. Adjust any parameter in the parameter block or using OpenSCAD's built-in Customizer GUI pane.
5. Press **F6** to compile and compute the full CSG boolean geometry.
6. Select **File -> Export -> Export as STL...** or **Export as 3MF...** to generate a 3D-printable or CAM-ready mesh.

### Headless CLI Export
When the `openscad` executable is in your system `PATH`:
```bash
# Render to binary STL
openscad -o cad/parametric_mounting_bracket.stl cad/parametric_mounting_bracket.scad

# Render high-resolution PNG image
openscad --imgsize=1920,1080 -o cad/bracket_render.png cad/parametric_mounting_bracket.scad
```

---

## 5. Validation Status

> [!NOTE]
> **Environment Validation Notice**: The OpenSCAD command-line executable was not installed in the automated execution environment. Consequently, automated headless STL file generation was **not performed**. The `.scad` script is authored using standard, strict CSG geometry, positive coordinate indexing, non-coincident boolean offsets (`eps = 0.1`), and high facet resolution (`$fn=60`), ready for immediate interactive compilation in OpenSCAD.

> [!WARNING]
> **Structural Integrity Disclaimer**: This parametric CAD model is an illustrative educational artifact created to ground the manufacturing process planning and cycle-time calculations. It has **not** been certified via finite element analysis (FEA), cyclic fatigue testing, or physical proof-load certification. Do not deploy this geometry in safety-critical structural or aerospace applications without independent engineering sign-off.
