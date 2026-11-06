#include "removable_latch.h"
#include <cassert>
#include <limits>
#include <cstdio>

int main() {
    ContainerLatch l; bool departed = false;
    auto step = [&](float radial, float height, bool held=true, bool locked=false) {
        return UpdateRemovableLatch(l, departed, radial, height, .38f, held, locked);
    };
    step(0, 0); assert(!l.latched && !departed); // New grab opens, even inside capture zone.
    step(0, .12f); assert(!l.latched && !departed);
    step(0, .20f); assert(!l.latched && departed);
    step(.34f, .08f); assert(l.latched && !departed); // Rim approach while still held.
    step(.6f, .4f); assert(l.latched); // Same grab cannot pull a captured lid away.
    step(0, 0, false); step(0, 0); assert(!l.latched); // Release and grab again opens.
    step(.5f, 0); assert(departed && !l.latched); // Sideways removal clears capture zone.
    step(.5f, 0, false); assert(!l.latched); // Released away from container stays free.
    step(.1f, -.5f, false); assert(!l.latched); // No teleport through bottom/walls.
    step(.2f, .09f, false); assert(l.latched); // Released falling lid can land near rim.
    step(0, 0); step(0, .3f); step(0, 0, true, true); assert(l.latched); // Lock wins.
    step(0, 0, false); step(0, 0); step(0, .3f);
    step(std::numeric_limits<float>::quiet_NaN(), 0); assert(!l.latched);
    step(0, std::numeric_limits<float>::infinity()); assert(!l.latched);
    for (float r : {.08f,.2f,.7f}) {
        ContainerLatch a; bool d=false;
        UpdateRemovableLatch(a,d,0,0,r,true,false);
        UpdateRemovableLatch(a,d,0,.25f,r,true,false);
        UpdateRemovableLatch(a,d,r-.01f,.04f,r,true,false);
        assert(a.latched);
    }
    puts("PASS: rim capture, orientation-independent input, held/released closure, departure hysteresis, next-grab unlock, below-rim guard, locks and invalid inputs");
}
