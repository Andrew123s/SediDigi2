#pragma once

// Jetson-side C++ client for the Pico WS2812 panel server.
// Talks the line-based USB serial protocol specified in README.md
// (section "USB Serial Protocol").
//
// Reference usage:
//   PicoLink p;
//   std::string r = p.set_color("0062ac", 40);  // "OK"
//   r = p.ping();                                // "PONG"
//   p.off();                                     // "OK"

#include <cstring>
#include <stdexcept>
#include <string>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

class PicoLink {
public:
    explicit PicoLink(const char* device = "/dev/ttyACM0", int timeout_s = 2) {
        fd_ = ::open(device, O_RDWR | O_NOCTTY | O_NONBLOCK);
        if (fd_ < 0)
            throw std::runtime_error(std::string("open ") + device + " failed");

        struct termios tio;
        std::memset(&tio, 0, sizeof(tio));
        tcgetattr(fd_, &tio);
        cfmakeraw(&tio);
        cfsetspeed(&tio, B115200);  // baud is ignored by USB CDC
        tio.c_cc[VMIN] = 1;
        tio.c_cc[VTIME] = timeout_s * 10;  // deci-seconds
        tcsetattr(fd_, TCSANOW, &tio);
        ::fcntl(fd_, F_SETFL, 0);  // blocking after open
    }

    ~PicoLink() { close(); }

    PicoLink(const PicoLink&) = delete;
    PicoLink& operator=(const PicoLink&) = delete;

    std::string send(const std::string& cmd) {
        std::string line = cmd + "\n";
        ::write(fd_, line.data(), line.size());

        std::string resp;
        char c;
        while (::read(fd_, &c, 1) == 1) {
            if (c == '\n') break;
            resp += c;
        }
        return resp;
    }

    std::string set_color(const std::string& hex, int brightness) {
        return send("SET " + hex + " " + std::to_string(brightness));
    }
    std::string off() { return send("OFF"); }
    std::string ping() { return send("PING"); }
    std::string version() { return send("VERSION"); }

    void close() {
        if (fd_ >= 0) {
            ::close(fd_);
            fd_ = -1;
        }
    }

private:
    int fd_ = -1;
};
