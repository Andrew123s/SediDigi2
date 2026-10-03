// Measure geometric and intensity properties of the regions found in a
// binary image (8-bit, single channel; foreground = non-zero).
//
// Embeddable library: no file I/O, no main(). Compile this file together
// with the calling code (e.g. `g++ main.cpp contour_measure.cpp ...`) or
// `#include "contour_measure.cpp"` from a translation unit that provides
// main(). All public functions live in the `contour` namespace.
//
// Conventions:
//   * Contour functions take a non-empty closed contour as
//     std::vector<cv::Point>; an empty contour throws std::invalid_argument.
//   * A value that cannot be computed for a contour is NaN
//     (std::numeric_limits<double>::quiet_NaN()).
//   * Derived ratios (solidity, aspect ratio, extent, equivalent diameter)
//     exist both as contour functions and as `*_from` helpers that take the
//     already measured inputs.
//   * Intensity functions take the binary cv::Mat (CV_8UC1) in addition.
//
// The measured features follow the OpenCV tutorials "Contour Features" and
// "Contour Properties":
//
//   https://docs.opencv.org/3.4.20/dd/d49/tutorial_py_contour_features.html
//   https://docs.opencv.org/3.4.20/d1/d32/tutorial_py_contour_properties.html

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace contour {
namespace detail {

constexpr double kPi = 3.14159265358979323846;
constexpr double kApproxEpsilon = 0.01;  // fraction of the arc length

inline double qnan() { return std::numeric_limits<double>::quiet_NaN(); }

// Throw if the contour is empty.
inline void require_contour(const std::vector<cv::Point>& contour) {
    if (contour.empty()) {
        throw std::invalid_argument("contour must not be empty");
    }
}

// Filled binary mask of the contour region; also checks that binary is CV_8UC1.
inline cv::Mat filled_mask(const cv::Mat& binary,
                           const std::vector<cv::Point>& contour) {
    if (binary.type() != CV_8UC1) {
        throw std::invalid_argument("binary image must be 8-bit single channel");
    }
    cv::Mat mask = cv::Mat::zeros(binary.size(), CV_8UC1);
    cv::drawContours(mask, std::vector<std::vector<cv::Point>>{contour}, -1,
                     255, cv::FILLED);
    return mask;
}

// A cv::RotatedRect whose center, size and angle are all NaN ("not computable").
inline cv::RotatedRect nan_rotated_rect() {
    cv::RotatedRect rr;
    rr.center = cv::Point2f(static_cast<float>(qnan()), static_cast<float>(qnan()));
    rr.size = cv::Size2f(static_cast<float>(qnan()), static_cast<float>(qnan()));
    rr.angle = static_cast<float>(qnan());
    return rr;
}

}  // namespace detail

// The extreme contour points: topmost, bottommost, leftmost and rightmost.
struct ExtremePoints {
    cv::Point top;
    cv::Point bottom;
    cv::Point left;
    cv::Point right;
};

// The min/max intensity inside a contour and their locations.
struct MinMaxIntensity {
    double min;
    double max;
    cv::Point min_loc;
    cv::Point max_loc;
};

// ----------------------------------------------------------------------------

// Outer contours of all non-zero regions (RETR_EXTERNAL, CHAIN_APPROX_SIMPLE).
inline std::vector<std::vector<cv::Point>> find_contours(const cv::Mat& binary) {
    if (binary.type() != CV_8UC1) {
        throw std::invalid_argument("binary image must be 8-bit single channel");
    }
    std::vector<std::vector<cv::Point>> contours;
    // findContours may modify its input image on older OpenCV versions;
    // operate on a copy so the caller's image is never touched.
    cv::Mat work = binary.clone();
    cv::findContours(work, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    return contours;
}

// --- Moments and centroid ---------------------------------------------------

// Image moments of a contour up to the third order (cv::Moments).
inline cv::Moments moments(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::moments(contour);
}

// Centroid (center of mass); (NaN, NaN) if the contour area m00 is zero.
inline cv::Point2d centroid(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    const cv::Moments m = cv::moments(contour);
    if (m.m00 != 0.0) {
        return cv::Point2d(m.m10 / m.m00, m.m01 / m.m00);
    }
    return cv::Point2d(detail::qnan(), detail::qnan());
}

// --- Basic shape ------------------------------------------------------------

// Polygon area of the contour (cv::contourArea, absolute value).
inline double area(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return std::fabs(cv::contourArea(contour));
}

// Perimeter (arc length) of the closed contour.
inline double perimeter(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::arcLength(contour, true);
}

// --- Approximation -----------------------------------------------------------

// Douglas-Peucker epsilon: kApproxEpsilon times the perimeter.
inline double approx_epsilon(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return detail::kApproxEpsilon * cv::arcLength(contour, true);
}

// Douglas-Peucker approximation of the contour.
inline std::vector<cv::Point> approx_poly(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    std::vector<cv::Point> approx;
    cv::approxPolyDP(contour, approx, approx_epsilon(contour), true);
    return approx;
}

// --- Convexity ---------------------------------------------------------------

// Convex hull of the contour.
inline std::vector<cv::Point> convex_hull(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    std::vector<cv::Point> hull;
    cv::convexHull(contour, hull);
    return hull;
}

// Polygon area of the convex hull (absolute value).
inline double hull_area(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return std::fabs(cv::contourArea(convex_hull(contour)));
}

// Whether the contour is convex.
inline bool is_convex(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::isContourConvex(contour);
}

// Derived: area / hull area; NaN if the hull area is zero.
inline double solidity_from(double area_value, double hull_area_value) {
    return hull_area_value > 0.0 ? area_value / hull_area_value
                                 : detail::qnan();
}

// Solidity: area / convex hull area; NaN if the hull area is zero.
inline double solidity(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return solidity_from(area(contour), hull_area(contour));
}

// --- Bounding rectangle ------------------------------------------------------

// Up-right bounding rectangle of the contour.
inline cv::Rect bounding_rect(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::boundingRect(contour);
}

// Derived: width / height of a bounding rectangle; NaN if the height is zero.
inline double aspect_ratio_from(const cv::Rect& rect) {
    return rect.height > 0 ? static_cast<double>(rect.width) / rect.height
                           : detail::qnan();
}

// Bounding-rectangle aspect ratio (width / height); NaN for a zero height.
inline double aspect_ratio(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return aspect_ratio_from(bounding_rect(contour));
}

// Derived: area / (rect width * rect height); NaN if a rect side is zero.
inline double extent_from(double area_value, const cv::Rect& rect) {
    if (rect.width > 0 && rect.height > 0) {
        return area_value / (static_cast<double>(rect.width) * rect.height);
    }
    return detail::qnan();
}

// Extent: area / bounding rectangle area; NaN if a rect side is zero.
inline double extent(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return extent_from(area(contour), bounding_rect(contour));
}

// --- Rotated rectangle -------------------------------------------------------

// Minimum-area rotated rectangle around the contour; NaN values for fewer
// than 2 points.
inline cv::RotatedRect min_area_rect(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    if (contour.size() < 2) {
        return detail::nan_rotated_rect();
    }
    return cv::minAreaRect(contour);
}

// --- Enclosing circle --------------------------------------------------------

// Minimum area circle (center, radius); NaN values for fewer than 2 points.
inline std::pair<cv::Point2f, float> min_enclosing_circle(
    const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    if (contour.size() < 2) {
        return {cv::Point2f(static_cast<float>(detail::qnan()),
                            static_cast<float>(detail::qnan())),
                static_cast<float>(detail::qnan())};
    }
    cv::Point2f center;
    float radius = 0.0f;
    cv::minEnclosingCircle(contour, center, radius);
    return {center, radius};
}

// --- Ellipse and line fitting ------------------------------------------------

// Ellipse fitted to the contour (center, axes, angle); NaN values for fewer
// than 5 points.
inline cv::RotatedRect fit_ellipse(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    if (contour.size() < 5) {
        return detail::nan_rotated_rect();
    }
    return cv::fitEllipse(contour);
}

// Line fitted to the contour (vx, vy, px, py); NaN values for fewer than 2
// points.
inline cv::Vec4f fit_line(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    if (contour.size() < 2) {
        return cv::Vec4f(static_cast<float>(detail::qnan()),
                         static_cast<float>(detail::qnan()),
                         static_cast<float>(detail::qnan()),
                         static_cast<float>(detail::qnan()));
    }
    cv::Vec4f line;
    cv::fitLine(contour, line, cv::DIST_L2, 0, 0.01, 0.01);
    return line;
}

// Direction angle of a fitted line in degrees (atan2(vy, vx)).
inline double line_angle_deg(double vx, double vy) {
    return std::atan2(vy, vx) * 180.0 / detail::kPi;
}

// --- Derived measures --------------------------------------------------------

// Derived: diameter of a circle with the given area; 0 if the area is zero.
inline double equivalent_diameter_from(double area_value) {
    if (area_value > 0.0) {
        return std::sqrt(4.0 * area_value / detail::kPi);
    }
    return 0.0;
}

// Equivalent diameter of the contour: sqrt(4 * area / pi); 0 if the area is
// zero.
inline double equivalent_diameter(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return equivalent_diameter_from(area(contour));
}

// --- Extreme points ----------------------------------------------------------

// Extreme points of the contour (top, bottom, left, right).
inline ExtremePoints extreme_points(const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    ExtremePoints ext{contour[0], contour[0], contour[0], contour[0]};
    for (const cv::Point& p : contour) {
        if (p.y < ext.top.y) {
            ext.top = p;
        }
        if (p.y > ext.bottom.y) {
            ext.bottom = p;
        }
        if (p.x < ext.left.x) {
            ext.left = p;
        }
        if (p.x > ext.right.x) {
            ext.right = p;
        }
    }
    return ext;
}

// --- Intensity (requires the binary image) -----------------------------------

// Filled binary mask of the contour region (same size as binary).
inline cv::Mat mask(const cv::Mat& binary,
                    const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return detail::filled_mask(binary, contour);
}

// Number of pixels inside the contour (filled mask).
inline int pixel_count(const cv::Mat& binary,
                       const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::countNonZero(detail::filled_mask(binary, contour));
}

// Mean intensity of binary inside the contour; the foreground value for a
// binary input.
inline double mean_intensity(const cv::Mat& binary,
                             const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    return cv::mean(binary, detail::filled_mask(binary, contour))[0];
}

// Min/max intensity and their locations inside the contour; NaN / Point(0, 0)
// if no pixels are masked.
inline MinMaxIntensity min_max_intensity(
    const cv::Mat& binary, const std::vector<cv::Point>& contour) {
    detail::require_contour(contour);
    const cv::Mat msk = detail::filled_mask(binary, contour);
    MinMaxIntensity r;
    if (cv::countNonZero(msk) == 0) {
        r.min = detail::qnan();
        r.max = detail::qnan();
        r.min_loc = cv::Point(0, 0);
        r.max_loc = cv::Point(0, 0);
        return r;
    }
    cv::minMaxLoc(binary, &r.min, &r.max, &r.min_loc, &r.max_loc, msk);
    return r;
}

}  // namespace contour