// snippet_effect_sequence.cpp - Minimal C++ example to trigger a sequence of
// haptic effects via the hapticd daemon using the installed haptic-cli command.
//
// Code example (not necessarily compilable) - mirrors snippet_effect_sequence.py.

#include <cstdlib>
#include <string>

int main() {
    // --- Configuration ---
    const std::string channel = "0";             // MUX channel(s): 0-3, combination (e.g. 0+2), or "all"
    // channel = "0+2";                          // e.g. broadcast sequence to channels 0 and 2 simultaneously
    const std::string sequence = "short_long";   // Sequence name (see EFFECT_SEQUENCES), e.g. "short_long"

    // --- Send command via haptic-cli ---
    std::string cmd = "haptic-cli --channel " + channel + " --effect " + sequence;
    return std::system(cmd.c_str());
}
