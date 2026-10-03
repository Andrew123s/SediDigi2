// Measure the sharpness of a digital image using the Tenengrad focus measure.
//
// C++ counterpart of focus_measure.py. For a single input image file this
// program prints one scalar score (higher = sharper).
//
// Tenengrad focus measure:
//
//     F = (1 / N) * sum(Ix^2 + Iy^2)
//
// with Ix, Iy being the Sobel gradient components of the grayscale image and
// N the number of pixels used.

#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/core.hpp>

#include <cstdio>
#include <string>
#include <cmath>

struct Config {
    std::string image;
    double      scale = 1.0;
    std::string roi = "full";
    double      roi_fraction = 0.8;
    bool        json = false;
};

static void print_usage(const char* prog) {
    std::printf(
        "Usage: %s <image> [--scale F] [--roi {full|center}] \n"
        "                 [--roi-fraction F] [--json]\n"
        "\n"
        "Compute the Tenengrad sharpness score of an image. One score per\n"
        "image; higher is sharper.\n"
        "\n"
        "  <image>          Path to the input image file\n"
        "  --scale F        Downscale factor (e.g. 0.5 halves each dimension,\n"
        "                   default: 1.0)\n"
        "  --roi R          Region of interest: full or center (default: full)\n"
        "  --roi-fraction F Side length of the center crop as a fraction of\n"
        "                   the smaller image side (default: 0.8)\n"
        "  --json           Print the score as a single JSON object\n",
        prog);
}

static bool parse_args(int argc, char** argv, Config& cfg) {
    if (argc < 2) {
        print_usage(argv[0]);
        return false;
    }
    cfg.image = argv[1];

    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--scale" && i + 1 < argc) {
            cfg.scale = std::atof(argv[++i]);
        } else if (arg == "--roi" && i + 1 < argc) {
            cfg.roi = argv[++i];
            if (cfg.roi != "full" && cfg.roi != "center") {
                std::fprintf(stderr, "error: --roi must be 'full' or 'center'\n");
                return false;
            }
        } else if (arg == "--roi-fraction" && i + 1 < argc) {
            cfg.roi_fraction = std::atof(argv[++i]);
        } else if (arg == "--json") {
            cfg.json = true;
        } else {
            std::fprintf(stderr, "error: unknown argument: %s\n", arg.c_str());
            return false;
        }
    }
    return true;
}

static double tenengrad(const cv::Mat& gray) {
    cv::Mat sobel_x, sobel_y;
    cv::Sobel(gray, sobel_x, CV_64F, 1, 0, 3);
    cv::Sobel(gray, sobel_y, CV_64F, 0, 1, 3);
    cv::Mat energy = sobel_x.mul(sobel_x) + sobel_y.mul(sobel_y);
    return cv::mean(energy)[0];
}

static cv::Mat center_crop(const cv::Mat& gray, double fraction) {
    if (!(fraction > 0.0 && fraction <= 1.0)) {
        std::fprintf(stderr, "error: --roi-fraction must be in the range (0, 1]\n");
        std::exit(1);
    }
    const int h = gray.rows;
    const int w = gray.cols;
    const int side = static_cast<int>(std::lround(fraction * std::min(h, w)));
    const int x0 = (w - side) / 2;
    const int y0 = (h - side) / 2;
    return gray(cv::Rect(x0, y0, side, side)).clone();
}

int main(int argc, char** argv) {
    Config cfg;
    if (!parse_args(argc, argv, cfg)) {
        return 1;
    }
    if (cfg.scale <= 0.0 || cfg.scale > 1.0) {
        std::fprintf(stderr, "error: --scale must be in the range (0, 1]\n");
        return 1;
    }

    cv::Mat gray = cv::imread(cfg.image, cv::IMREAD_GRAYSCALE);
    if (gray.empty()) {
        std::fprintf(stderr, "error: could not read image: %s\n", cfg.image.c_str());
        return 1;
    }

    if (cfg.scale != 1.0) {
        const int new_width = std::max(1, static_cast<int>(std::lround(gray.cols * cfg.scale)));
        const int new_height = std::max(1, static_cast<int>(std::lround(gray.rows * cfg.scale)));
        cv::resize(gray, gray, cv::Size(new_width, new_height), 0.0, 0.0, cv::INTER_AREA);
    }

    if (cfg.roi == "center") {
        gray = center_crop(gray, cfg.roi_fraction);
    }

    const double score = tenengrad(gray);

    if (cfg.json) {
        std::printf(
            "{\n"
            "  \"image\": \"%s\",\n"
            "  \"score\": %.6f,\n"
            "  \"width\": %d,\n"
            "  \"height\": %d,\n"
            "  \"region\": \"%s\",\n"
            "  \"scale\": %g\n"
            "}\n",
            cfg.image.c_str(), score, gray.cols, gray.rows, cfg.roi.c_str(), cfg.scale);
    } else {
        std::printf("%.6f\n", score);
    }

    return 0;
}
