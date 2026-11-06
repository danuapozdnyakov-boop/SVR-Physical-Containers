#pragma once
#include <algorithm>
#include <cmath>
#include "latch.h"

// Distances are between the moving lid's COM and its closed COM, in Havok metres.
// Orientation is deliberately absent: the seated pose is restored after capture.
inline bool UpdateRemovableLatch(ContainerLatch& latch, bool& departed,
                                 float radial, float height, float radius,
                                 bool held, bool locked) {
    const bool fresh = held && !latch.wasHeld;
    const bool wasLatched = latch.latched;
    if (fresh && !locked) { latch.latched = false; departed = false; }
    const float captureRadius = std::clamp(radius, .08f, .70f);
    constexpr float captureHeight = .10f;
    const bool finite = std::isfinite(radial) && std::isfinite(height);
    if (!latch.latched && finite &&
        (radial > captureRadius + .06f || std::abs(height) > captureHeight + .06f))
        departed = true;
    // A lid must first leave the capture zone, otherwise a fresh grab would relatch instantly.
    // Do not snap a fallen lid up through the container from below its opening.
    if (locked || (!latch.latched && departed && finite &&
                   radial <= captureRadius && height >= -.04f && height <= captureHeight)) {
        latch.latched = true;
        departed = false;
    }
    latch.wasHeld = held;
    return !wasLatched && latch.latched;
}
