// =============================================================================
// CellForge Manufacturing Lab: Parametric Industrial Mounting Bracket
// Component: Heavy-Duty Structural L-Bracket with Reinforcing Gusset & Pockets
// Units: Millimeters (mm)
// Target Manufacturing Routes:
//   Route A: CNC Machining from 6061-T6 Aluminum Billet
//   Route B: Metal Additive Manufacturing (LPBF / AlSi10Mg) with CNC Finishing
// =============================================================================

/* [Principal Dimensions (mm)] */
bracket_width = 60.0;       // Total bracket width across Y-axis
base_length = 80.0;         // Length of base mounting foot along X-axis
flange_height = 70.0;       // Height of vertical mounting flange along Z-axis
wall_thickness = 8.0;       // Nominal wall thickness of base and vertical flange
gusset_thickness = 6.0;     // Thickness of triangular structural stiffening ribs

/* [Fastener Mounting Holes (mm)] */
// ISO 273 Medium Fit Clearance Holes
base_hole_dia = 6.6;        // M6 clearance hole diameter (base plate)
flange_hole_dia = 9.0;      // M8 clearance hole diameter (vertical flange)
base_hole_pitch_x = 45.0;   // Spacing between base hole centers along X
base_hole_pitch_y = 38.0;   // Spacing between base hole centers along Y
flange_hole_pitch_z = 35.0; // Spacing between flange hole centers along Z
flange_hole_pitch_y = 38.0; // Spacing between flange hole centers along Y

/* [Design for Manufacturing Features] */
corner_fillet_radius = 6.0; // Outer corner blend radius (reduces stress concentration)
inner_fillet_radius = 4.0;  // Fillet radius at intersection of base and flange
enable_pockets = true;      // Enable weight-reduction pockets (Additive / 3D milling feature)
pocket_depth = 3.5;         // Depth of recessed pockets (mm)

/* [Rendering Quality] */
$fn = 60;                   // Circle facet resolution for smooth arcs and bores

// Small epsilon to guarantee clean boolean manifold cuts without coincident faces
eps = 0.1;

// =============================================================================
// Main Assembly Construction
// =============================================================================

module mounting_bracket() {
    difference() {
        // Positive Material Volume
        union() {
            // 1. Horizontal Base Plate
            base_plate();

            // 2. Vertical Mounting Flange
            vertical_flange();

            // 3. Structural Gusset Ribs (Reinforcing gussets at Y edges)
            gusset_ribs();

            // 4. Structural Internal Fillet
            inner_bend_fillet();
        }

        // Subtractive Volume: Mounting Bores & Lightening Pockets
        // 1. Base Plate Fastener Holes (4x M6 clearance)
        base_mounting_holes();

        // 2. Vertical Flange Fastener Holes (2x M8 clearance)
        flange_mounting_holes();

        // 3. Weight-Reduction Lightening Pockets
        if (enable_pockets) {
            lightening_pockets();
        }
    }
}

// =============================================================================
// Positive Geometry Modules
// =============================================================================

module base_plate() {
    // Filleted base plate
    hull() {
        // Inner edge near vertical wall
        translate([wall_thickness, 0, 0])
            cube([eps, bracket_width, wall_thickness]);

        // Outer corner fillets
        translate([base_length - corner_fillet_radius, corner_fillet_radius, 0])
            cylinder(r=corner_fillet_radius, h=wall_thickness);

        translate([base_length - corner_fillet_radius, bracket_width - corner_fillet_radius, 0])
            cylinder(r=corner_fillet_radius, h=wall_thickness);
    }
    // Solid junction zone
    cube([wall_thickness, bracket_width, wall_thickness]);
}

module vertical_flange() {
    // Filleted vertical flange
    hull() {
        // Bottom junction zone
        cube([wall_thickness, bracket_width, eps]);

        // Top corner fillets
        translate([0, corner_fillet_radius, flange_height - corner_fillet_radius])
            rotate([0, 90, 0])
            cylinder(r=corner_fillet_radius, h=wall_thickness);

        translate([0, bracket_width - corner_fillet_radius, flange_height - corner_fillet_radius])
            rotate([0, 90, 0])
            cylinder(r=corner_fillet_radius, h=wall_thickness);
    }
}

module gusset_ribs() {
    // Left Structural Gusset
    translate([wall_thickness, 0, wall_thickness])
        single_gusset();

    // Right Structural Gusset
    translate([wall_thickness, bracket_width - gusset_thickness, wall_thickness])
        single_gusset();
}

module single_gusset() {
    // Triangular gusset web
    gusset_x = base_length - wall_thickness - corner_fillet_radius;
    gusset_z = flange_height - wall_thickness - corner_fillet_radius;

    rotate([90, 0, 90])
        linear_extrude(height=gusset_thickness)
        polygon(points=[
            [0, 0],
            [gusset_z, 0],
            [0, gusset_x]
        ]);
}

module inner_bend_fillet() {
    // Reinforcing cylinder at the 90-degree internal corner
    translate([wall_thickness + inner_fillet_radius, 0, wall_thickness + inner_fillet_radius])
        difference() {
            translate([-inner_fillet_radius, 0, -inner_fillet_radius])
                cube([inner_fillet_radius, bracket_width, inner_fillet_radius]);

            rotate([-90, 0, 0])
                cylinder(r=inner_fillet_radius, h=bracket_width);
        }
}

// =============================================================================
// Subtractive Geometry Modules (Through Holes & Cuts)
// =============================================================================

module base_mounting_holes() {
    // 4x clearance holes in base plate (M6)
    center_y = bracket_width / 2.0;
    y1 = center_y - (base_hole_pitch_y / 2.0);
    y2 = center_y + (base_hole_pitch_y / 2.0);

    x_start = wall_thickness + (base_length - wall_thickness - base_hole_pitch_x) / 2.0;
    x1 = x_start;
    x2 = x_start + base_hole_pitch_x;

    for (x = [x1, x2]) {
        for (y = [y1, y2]) {
            translate([x, y, -eps])
                cylinder(d=base_hole_dia, h=wall_thickness + 2 * eps);
        }
    }
}

module flange_mounting_holes() {
    // 2x clearance holes in vertical flange (M8)
    center_y = bracket_width / 2.0;
    y1 = center_y - (flange_hole_pitch_y / 2.0);
    y2 = center_y + (flange_hole_pitch_y / 2.0);

    z_pos = wall_thickness + (flange_height - wall_thickness) / 2.0;

    for (y = [y1, y2]) {
        translate([-eps, y, z_pos])
            rotate([0, 90, 0])
            cylinder(d=flange_hole_dia, h=wall_thickness + 2 * eps);
    }
}

module lightening_pockets() {
    // Recessed pocket on back face of vertical flange (weight reduction / DfAM feature)
    pocket_w = bracket_width - (2 * corner_fillet_radius) - 4.0;
    pocket_h = flange_height - wall_thickness - (2 * corner_fillet_radius);

    if (pocket_w > 10 && pocket_h > 10) {
        translate([-eps, (bracket_width - pocket_w) / 2.0, wall_thickness + corner_fillet_radius])
            cube([pocket_depth + eps, pocket_w, pocket_h]);
    }
}

// Instantiate the component
mounting_bracket();
