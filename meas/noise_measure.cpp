// Measure pixel-wise sensor noise in an NV12 color frame.
//
// Embeddable library: no file I/O, no main(). Compile this file together
// with the calling code (e.g. `g++ main.cpp noise_measure.cpp ...`) or
// `#include "noise_measure.cpp"` from a translation unit that provides
// main(). All public functions live in the `noise` namespace.
//
// NV12 layout (width * height * 3 / 2 bytes):
//   * Y plane first: width*height bytes, row-major luma, full resolution.
//   * Then the 4:2:0 chroma block: width*height/2 bytes, interleaved
//     U,V,U,V,...; each of U and V is a (width/2) x (height/2) image once
//     deinterleaved.
//
// The noise is modelled as approximately additive zero-mean Gaussian
// ("sensor noise"): the estimators return its standard deviation sigma in
// gray levels. noise_index() normalizes sigma to a 0..1 "presence" scalar.
//
// Conventions:
//   * A frame is passed as (const uint8_t* buffer, int width, int height);
//     the buffer must point at width*height*3/2 contiguous bytes (the size
//     cannot be checked through a raw pointer and is the caller's contract).
//   * width and height must be at least 3, otherwise std::invalid_argument.
//   * A plane is a single-channel 8-bit cv::Mat (CV_8UC1); sigma functions
//     take such a plane (usually y_plane(...) or one of uv_planes(...)).
//   * Sigma is always >= 0; a perfectly flat plane yields (close to) 0.
//   * No NaN cases: input errors throw std::invalid_argument.
//
// Heuristic caveat: NV12 Y is gamma-corrected and already filtered in-camera,
// so this estimates a perceived gray-level noise strength, not the true
// photon-shot-noise sigma. mad_sigma() is the robust counterpart to
// immerkaer_sigma() (less biased by image texture); Immerkaer tends to
// underestimate for very weak noise and to overestimate on strong structure.
//
// Based on J. Immerkaer, "Fast Noise Variance Estimation", Computer Vision
// and Image Understanding, vol. 64, no. 2, pp. 300-302, 1996.

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <stdexcept>
#include <vector>

namespace noise {
namespace detail {

constexpr double kSqrtPiOver2 = 1.2533141373155003;  // sqrt(pi / 2)
constexpr double kMadScale = 1.4826;  // MAD -> sigma for a Gaussian
constexpr int kEdge = 1;  // fully valid interior after the 3x3 convolution

// Throw if the pointer/dimensions do not describe a valid NV12 frame.
inline void require_nv12(const uint8_t* buffer, int width, int height) {
    if (buffer == nullptr) {
        throw std::invalid_argument("NV12 buffer must not be null");
    }
    if (width < 3 || height < 3) {
        throw std::invalid_argument("width and height must be at least 3");
    }
}

// Throw if plane is not a 3x3-or-larger 8-bit single-channel image.
inline void require_plane(const cv::Mat& plane) {
    if (plane.type() != CV_8UC1) {
        throw std::invalid_argument("plane must be 8-bit single channel");
    }
    if (plane.cols < 3 || plane.rows < 3) {
        throw std::invalid_argument("plane must be at least 3x3 pixels");
    }
}

// |I * F| on the fully valid interior of the Immerkaer high-pass mask F.
// The interior depends only on real pixels, so the border mode is
// irrelevant to the result (BORDER_REPLICATE only fills the unused rim).
inline cv::Mat highpass_abs(const cv::Mat& plane) {
    require_plane(plane);
    const cv::Mat kernel = (cv::Mat_<double>(3, 3) << 1, -2, 1, -2, 4, -2, 1,
                            -2, 1);
    cv::Mat source;
    plane.convertTo(source, CV_64F);
    cv::Mat response;
    cv::filter2D(source, response, CV_64F, kernel, cv::Point(-1, -1), 0.0,
                 cv::BORDER_REPLICATE);
    cv::Mat interior(response, cv::Rect(kEdge, kEdge, response.cols - 2 * kEdge,
                                        response.rows - 2 * kEdge));
    cv::Mat absolute = cv::abs(interior);
    return absolute;
}

}  // namespace detail

// --- NV12 plane extraction ---------------------------------------------------

// The Y (luma) plane of an NV12 frame as a (height, width) CV_8UC1 view of
// the original buffer (zero copy).
inline cv::Mat y_plane(const uint8_t* buffer, int width, int height) {
    detail::require_nv12(buffer, width, height);
    return cv::Mat(height, width, CV_8UC1, const_cast<uint8_t*>(buffer));
}

// The U and V planes of an NV12 frame as separate (width/2 x height/2)
// CV_8UC1 images (deinterleaved 4:2:0 chroma).
struct UvPlanes {
    cv::Mat u;
    cv::Mat v;
};

inline UvPlanes uv_planes(const uint8_t* buffer, int width, int height) {
    detail::require_nv12(buffer, width, height);
    const cv::Mat chroma(height / 2, width / 2, CV_8UC2,
                         const_cast<uint8_t*>(buffer +
                                              (std::size_t)width * height));
    std::vector<cv::Mat> channels;
    cv::split(chroma, channels);
    UvPlanes planes;
    planes.u = channels[0].clone();
    planes.v = channels[1].clone();
    return planes;
}

// --- Noise estimators --------------------------------------------------------

// Estimate of the Gaussian noise sigma in gray levels: one high-pass
// convolution, |r| summed over the valid interior and scaled by
// sqrt(pi/2) / (6 * (W-2) * (H-2)) (Immerkaer 1996).
inline double immerkaer_sigma(const cv::Mat& plane) {
    const cv::Mat response = detail::highpass_abs(plane);
    const double total = cv::sum(response)[0];
    return detail::kSqrtPiOver2 * total /
           (6.0 * response.cols * response.rows);
}

// Robust estimate of the Gaussian noise sigma in gray levels: the median of
// |r| on the valid interior, scaled by 1.4826 / 6. Shares its single
// convolution with immerkaer_sigma; less biased by image texture.
inline double mad_sigma(const cv::Mat& plane) {
    const cv::Mat response = detail::highpass_abs(plane);
    std::vector<double> values(response.begin<double>(),
                               response.end<double>());
    const size_t n = values.size();
    if (n == 0) {
        return 0.0;
    }
    const size_t mid = n / 2;
    std::nth_element(values.begin(), values.begin() + mid, values.end());
    double median = values[mid];
    if (n % 2 == 0) {
        const double lower =
            *std::max_element(values.begin(), values.begin() + mid);
        median = 0.5 * (lower + median);
    }
    return detail::kMadScale / 6.0 * median;
}

// Normalized noise presence: sigma / 255, i.e. roughly 0..1 of the full
// gray-level range.
inline double noise_index(double sigma) { return sigma / 255.0; }

}  // namespace noise