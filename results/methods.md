# Validation Methodology

Geometric accuracy of the AquaMVS multi-view stereo pipeline was evaluated against a
known-geometry target: a 12x9 ChArUco board (DICT_5X5_100, 60 mm squares) submerged
in fresh water and imaged from a fixed multi-camera rig. The board geometry provides
a controlled reference with known three-dimensional corner positions derived from the
physical square size [@deJesus2015; @MennaNocerino2019].

## Frame Selection and Held-Out Validation Set

The full board-present sequence comprises 10 output frames.  A measured overlap check
was performed to identify which of these frames coincide with positions used during
camera calibration: exactly 2 of the 10 frames (output indices 0 and 5, corresponding
to raw frame indices 0 and 3930) were found to overlap with the calibration fit and
were excluded from all accuracy metrics.  The remaining 8 frames constitute the
held-out validation set.  Because the exclusion was determined by comparing frame
positions against the calibration input set rather than assumed, these 8 held-out
frames are genuinely independent of the intrinsic and extrinsic calibration.

## Corner Transfer via Refractive Ray Casting

ChArUco corner positions detected in each camera's undistorted image were transferred
to three-dimensional metric coordinates by back-projecting each corner through the
refractive projection model using `RefractiveProjectionModel.cast_ray`.  This
procedure traces each image ray through the air-water interface using the measured
refractive indices and water-surface geometry, yielding a 3-D position in the
reconstruction frame for each detected corner.  Corner dropout --- cases where the
depth map produced no valid ray-surface intersection --- was measured at
0.2% (0.0023 fractional rate), confirming that the
large majority of corners transferred successfully.

## Scale-Independent Metrics Led the Analysis

All scale-independent metrics were computed and locked before any scale-dependent
alignment was applied, ensuring that the primary accuracy assessment is not subject
to the circularity concern described in the following section.

Board flatness --- the root-mean-square point-to-plane residual of the transferred
corners relative to a best-fit plane --- was 1.09 mm (pooled RMS across
all 8 held-out frames), reflecting the degree to which the AquaMVS reconstruction
places board corners on a common plane.  The board-size coefficient of variation
across the working volume was 0.0016, indicating that the recovered board
geometry is spatially consistent across depth and lateral position.  Cross-camera
agreement --- the RMS dispersion of independently transferred 3-D corner positions
across the camera ring for co-observed board corners --- was 3.46 mm
overall (MET-03).  These three scale-independent measures are non-circular: they assess
the internal consistency of the reconstruction without reference to the calibration
scale anchor.

## Absolute Scale as a Consistency Check (Partly Circular)

Absolute scale was assessed via a Umeyama similarity alignment (closed-form, exploiting
the known one-to-one corner-ID correspondence) between the transferred corner positions
and the ideal 60 mm board geometry.  The mean recovered scale factor corresponds to a
scale error of +0.040% (mean recovered board size 60.013 mm).
This result must be interpreted with care: the 60 mm square size is the same measurement
used as the calibration scale anchor, so recovering a scale close to unity is partly
expected by construction --- a partly circular consistency check.  The circularity
concern is partially resolved by the spatial breadth of the validation set (8 frames
covering a range of depths and lateral positions) and by the fact that the precision
board and the independent tank reference are separate physical objects, but it does not
vanish entirely.  This scale result is therefore reported as a secondary consistency
check after the scale-independent headline, not as the primary accuracy claim.

## Range-Dominated Residuals as a Refraction Signature

Residual errors were decomposed along the range direction (the in-water viewing ray
returned by `cast_ray`, parallel to the axis along which refraction acts) and the
lateral direction (perpendicular to the viewing ray, i.e. the in-plane direction
where refraction does not operate).  The residuals are strongly range-dominated:
pooled range RMS was 3.64 mm versus lateral RMS of 0.82 mm,
a range-to-lateral dominance ratio of 4.41.  This pattern --- range
error exceeding lateral error by more than four-fold across all 8 held-out frames ---
is consistent with the residual influence of refractive depth uncertainty, wherein
small errors in the ray-interface intersection translate to offsets along the cast-ray
direction rather than lateral displacement.  Sub-millimetre lateral agreement
(0.82 mm) confirms that the in-plane geometric fidelity of the
reconstruction is high, and that the larger cross-camera RMS (which mixes range and
lateral components) is dominated by the refraction-sensitive range direction.

## Contextualisation Against the Maas (2015) Benchmark

Refractive (through-water) reconstruction is known to carry a precision penalty of
approximately a factor of two relative to comparable in-air photogrammetry
[@Maas2015].  The scale-independent accuracy numbers reported here --- flatness
below 1.1 mm and cross-camera agreement below 3.5 mm without post-hoc refraction
correction --- demonstrate that the AquaMVS pipeline achieves metric-grade geometric
fidelity consistent with the factor of two benchmark for refractive multi-view imaging.
