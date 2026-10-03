// snippet_single_effect.cpp - Minimal C++ example to trigger a single haptic
// effect via the hapticd daemon using the installed haptic-cli command.
//
// Code example (not necessarily compilable) - mirrors snippet_single_effect.py.

#include <cstdlib>
#include <string>

int main() {
    // --- Configuration ---
    const std::string channel = "0";            // MUX channel(s): 0-3, combination (e.g. 0+2), or "all"
    // channel = "0+2";                         // e.g. broadcast to channels 0 and 2 simultaneously
    const std::string effect = "double_click";  // Effect name (e.g. "alert") or integer (e.g. 47)

    // --- Send command via haptic-cli ---
    std::string cmd = "haptic-cli --channel " + channel + " --effect " + effect;
    return std::system(cmd.c_str());
}
