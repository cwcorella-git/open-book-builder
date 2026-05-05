// Render back side
backplate = true;

// Render front side
bezel = true;

// Are you building a case for the Pi Pico based board?
abridged = false;

// Cut out holes for JST ports (only works on Abridged Edition at the moment)
jst = false;

// EXPERIMENTAL! Bevels the edge of the screen, but may print poorly without supports.
bevel_screen = true;

// The thickness of the PCB as fabricated
board_thickness = 1.0;

// How smooth the curves are
level_of_detail = 60;

// How thick you want the sidewalls to be
side_wall_thickness = 1.5;

// How thick you want the back wall to be
back_wall_thickness = 1.2;

// How far case should extend above PCB
front_thickness = 2.5;

// Added to holes and cavities to make sure things fit
xy_tolerance = 0.3;

// Added on the Z axis to account for 3D priting irregularities
z_tolerance = 0.3;

// The tallest part on the back of the board
tallest_part = abridged ? 5 : 4.5;

module _cylinderForHull(x, y, wall) {
    xsign = (x > 0) ? -1 : 1;
    ysign = (y > 0) ? -1 : 1;
    r = 3 + xy_tolerance + (wall ? side_wall_thickness : 0);
    h = board_thickness + tallest_part + (wall ? front_thickness + back_wall_thickness : 0);
    z = wall ? -back_wall_thickness - tallest_part : -tallest_part;
    translate([ xsign * 3 + x, ysign * 3 + y, z ]) cylinder(h, r, r, $fn = level_of_detail);
}

module _peg(x, y) {
    xsign = (x > 0) ? -1 : 1;
    ysign = (y > 0) ? -1 : 1;
    r = 3 + xy_tolerance;
    hull() {
        // main cylinder for peg, butts up to corner
        translate([ xsign * 3 + x, ysign * 3 + y, -tallest_part ]) cylinder(tallest_part - z_tolerance, r - xy_tolerance / 2, r - xy_tolerance / 2, $fn = level_of_detail);
        // extend toward the horizontal wall
        translate([ xsign * 1 + x, ysign * 1.5 * r + ysign + y, -tallest_part ]) cylinder(tallest_part - z_tolerance, 1, 1, $fn = level_of_detail);
        // extend toward the vertical wall
        translate([ xsign * 1.5 * r + xsign + x, ysign * 1 + y, -tallest_part ]) cylinder(tallest_part - z_tolerance, 1, 1, $fn = level_of_detail);
    }
}

module _screwhole(x, y) {
    xsign = (x > 0) ? -1 : 1;
    ysign = (y > 0) ? -1 : 1;
    r = (xy_tolerance + 2.5) / 2;
    // Countersunk hole for pan-head screw
    translate([ xsign * 3 + x, ysign * 3 + y, front_thickness + board_thickness - 1 ]) cylinder(1, 2.5, 2.5, $fn = level_of_detail);
    // Hole through front plate
    translate([ xsign * 3 + x, ysign * 3 + y, board_thickness - front_thickness + back_wall_thickness]) cylinder(front_thickness + z_tolerance, r - xy_tolerance / 2, r - xy_tolerance / 2, $fn = level_of_detail);
    // Slightly smaller hole in backplate
    translate([ xsign * 3 + x, ysign * 3 + y, board_thickness - front_thickness - tallest_part + board_thickness]) cylinder(tallest_part + board_thickness + front_thickness, r - xy_tolerance, r - xy_tolerance, $fn = level_of_detail);
}

module _roundedBoxForUSB(xdim, ydim, zdim, rdim) {
    hull() {
        translate([rdim,rdim,0]) cylinder(h=zdim,r=rdim, $fn=level_of_detail);
        translate([xdim-rdim,rdim,0]) cylinder(h=zdim,r=rdim, $fn=level_of_detail);
        translate([rdim,ydim-rdim,0]) cylinder(h=zdim,r=rdim, $fn=level_of_detail);
        translate([xdim-rdim,ydim-rdim,0]) cylinder(h=zdim,r=rdim, $fn=level_of_detail);
    }
}

module _button(x, y, angle, hole = false) {
    extra = hole ? 0.5 : 0;
    difference() {
        union () {
            translate([ x, y, board_thickness + (hole ? 4 : 3.2) / 2 ]) rotate([0, 0, angle]) cube([6 + extra, 3.5 + extra, hole ? 4 : 3.2], true);
            // this line was for when _button keepout was taller
            translate([ x, y, board_thickness + 0.0 / 2 ]) rotate([0, 0, angle]) cube([11, 2.54 + extra, 0.0], true);
            translate([ x, y, board_thickness + 0.0 ]) rotate([90, 0, angle]) translate([-3.5, 0, 0]) rotate([0, 180, 0]) cylinder(2.54, 2, 2, true, $fn=3);
            translate([ x, y, board_thickness + 0.0 ]) rotate([90, 0, angle]) translate([3.5, 0, 0]) cylinder(2.54, 2, 2, true, $fn=3);
            if (!hole) {
                translate([ x, y, board_thickness + 4 / 2 ]) rotate([0, 0, angle]) cube([2.75, 2, 4], true);
            }
        }
        translate([ x, y, -5 ]) cube([15, 10, 10], true);
    }
}

module jst_ph(x, y, width, hole = false) {
    extra = hole ? 0.2 : 0;
    translate([ x - (hole ? 5 : 0) + extra, y, -5.5 / 2 ]) cube([10 + (hole ? 10 : 0), width + extra, 5.5 + extra], true);
}

module holes() {
    union () {
        // front parts
        _button(20, 106, 0, true); // B3
        _button(65, 106, 0, true); // B4
        _button(36, 106, 90, true); // B5
        _button(42.5, 101, 0, true); // B6
        _button(42.5, 106, 0, true); // B7
        _button(42.5, 111, 0, true); // B8
        _button(49, 106, 90, true); // B9
        translate([ 0, 5.88, board_thickness ]) cube([78, 91.2, 1.5]); // screen thickness
        hull() {
            if (bevel_screen) {
                screen_bezel_extra = 6;
                // the -4.5 is exerimental, TODO work into final number when good
                translate([ 10, 7.88, board_thickness + side_wall_thickness - 0.01 ]) cube([65.5, 87, 0.01]); // screen active area
                translate([ 10 - (screen_bezel_extra / 2), 7.88 - (screen_bezel_extra / 2), board_thickness + front_thickness + 0.01 ]) cube([65 + screen_bezel_extra, 86.5 + screen_bezel_extra, 0.001]); // screen active area
            } else {
                translate([ 10, 7.88, board_thickness - 0.01 ]) cube([65.5, 87, 0.01]); // screen active area
                translate([ 10, 7.88, board_thickness + front_thickness + 0.01 ]) cube([65.5, 87, 0.001]); // screen active area
            }
        }
        // back parts

        // USB
        if (abridged) {
            translate([ 41, 1, -4.1 ]) rotate([ 90, 0, 0 ]) _roundedBoxForUSB(8.4,2.9,4.5,0.6);
        } else {
            translate([ 38.5, 1, -3.3 ]) rotate([ 90, 0, 0 ]) _roundedBoxForUSB(8.4,2.9,4.5,0.6);
        }

        // MicroSD card slot
        translate([ 84, 33.5, -1.75 ]) cube([10, 12, 1.8]);

        // accessory ports
        if (jst) {
            if (abridged) {
                jst_ph(5, 67, 10, true);
                jst_ph(5, 79.5, 10, true);
                // clear out the peg here, we'll add it back on the backplate
                translate([ .2, 73.25, -5.5 / 2 ]) cube([20, 3, 5.7], true);
            } else {
                // TODO: JST-SH ports on new bpok
            }
        }
        // AAA battery cutout
        if (abridged) {
            translate([ 18 - xy_tolerance, 53 - xy_tolerance, -tallest_part - back_wall_thickness ]) cube([56 + xy_tolerance * 2, 24 + xy_tolerance * 2, tallest_part]);
        }

        // cable routing
        translate([ -1, 41, 0 ]) cube( [ 2, 20, 2 ] );

        // on/off switch
        if (abridged) {
            hull() {
                 translate([ 85 - xy_tolerance, 91, -3 ]) cube([0.01, 4, 2], true);
                 translate([ 85 + side_wall_thickness + xy_tolerance, 91, -3 ]) cube([0.01, 10, 2], true);
            }
        }

        // reset button
        translate([ -xy_tolerance - 0.25, 91, -1.25 ]) cube([0.5, 4, 3], true);
        hull() {
            translate([ -xy_tolerance, 91, -1.25 ]) cube([0.01, 1, 0.75], true);
            translate([ -side_wall_thickness - xy_tolerance, 91, -1.25 ]) cube([0.01, 3.5, 1.75], true);
        }
        // Lock button cutouts:
        lock_button_tab_length = tallest_part + board_thickness;
        // cut out tab for lock button presser
        translate([ 75, -(side_wall_thickness + xy_tolerance) / 2, board_thickness - lock_button_tab_length / 2 ]) cube([8, side_wall_thickness + xy_tolerance, lock_button_tab_length], true);

        _screwhole(0, 0);
        _screwhole(85, 0);
        _screwhole(0, 115);
        _screwhole(85, 115);
    }
}

module case(backplate) {
    union() {
        difference() {
            difference() {
                union() {
                    hull() {
                        _cylinderForHull(0, 0, true);
                        _cylinderForHull(85, 0, true);
                        _cylinderForHull(0, 115, true);
                        _cylinderForHull(85, 115, true);
                    }
                }
                hull() {
                    _cylinderForHull(0, 0, false);
                    _cylinderForHull(85, 0, false);
                    _cylinderForHull(0, 115, false);
                    _cylinderForHull(85, 115, false);
                }
                holes();
            }
            translate([ -10, -10, -tallest_part ]) mirror([0, 0, backplate ? 0 : 1])
            cube([105, 135, 20]);
        }
        if (backplate) {
            // Pegs. board sits on these.
            difference() {
                union() {
                    _peg(0, 0);
                    _peg(85, 0);
                    _peg(0, 115);
                    _peg(85, 115);
                }
                union() {
                    _screwhole(0, 0);
                    _screwhole(85, 0);
                    _screwhole(0, 115);
                    _screwhole(85, 115);
                }
            }
            // Lock button pusher
            lock_button_tab_length = tallest_part + board_thickness - 0.5;
            // cut out tab for lock button presser
            translate([ 75, -(side_wall_thickness + xy_tolerance) * 3 / 4, board_thickness - lock_button_tab_length / 2 - 0.5 ]) cube([7, (side_wall_thickness + xy_tolerance) / 2, lock_button_tab_length], true);
            
            // failed idea, bottom support for lock button pusher
//            hull() {
//                translate([ 75, 2 - (side_wall_thickness + xy_tolerance) * 3 / 4, board_thickness - lock_button_tab_length - 0.5 ]) cube([7, 4 + (side_wall_thickness + xy_tolerance) / 2, .01], true);
//                translate([ 75, -(side_wall_thickness + xy_tolerance) * 3 / 4, board_thickness - lock_button_tab_length * 3 / 4 - 0.5 ]) cube([7, (side_wall_thickness + xy_tolerance) / 2, .01], true);
//            }
            // Battery box. ingress protection.
            if (abridged) {
                difference() {
                    // battery box body
                    translate([ 17, 52, -tallest_part - z_tolerance ]) cube([58, 26, tallest_part]);
                    // but hollowed out
                    translate([ 18 - xy_tolerance, 53 - xy_tolerance, -tallest_part - 1 ]) cube([56 + xy_tolerance * 2, 24 + xy_tolerance * 2, tallest_part + 2]);
                    // cutouts for solder pads
                    translate([ 13.5, 56.5, -1 ]) cube([65, 6, 1]);
                    translate([ 13.5, 67.5, -1 ]) cube([65, 6, 1]);
                }

                // BOOTSEL pin
                difference() {
                    translate([ 48.5, 12.5, -tallest_part - z_tolerance ]) cylinder(tallest_part - 4, 1.58, 1.58, $fn=level_of_detail);
                    translate([ 48.5, 12.5, -100 ]) cylinder(200, 1.08, 1.08, $fn=level_of_detail);
                }
                
                // JST ports
                if (jst) {
                    translate([ 5.2, 73.25, -5.5 / 2 ]) cube([14, 1.5, 5.7], true);
                }
            }
        } else {
        }
    }
}

if (bezel) {
    mirror([0, 1, 0]) { // flip coordinates to match KiCad
        translate([-5, -50, board_thickness + front_thickness]) rotate([ 180, 0, 180 ]) case(false);
    }
}

if (backplate) {
    mirror([0, 1, 0]) { // flip coordinates to match KiCad
        translate([5, -50, back_wall_thickness + tallest_part]) case(true);
    }
}

if (!(bezel || backplate)) {
    mirror([0, 1, 0]) { // flip coordinates to match KiCad
        case(true);
        case(false);
    }
}    
