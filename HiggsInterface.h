#pragma once

// RE::-adapted redeclaration of HIGGS's mod-support interface (higgsinterface001.h).
// The original is written against the legacy skse64 plugin framework; we consume it
// from CommonLibSSE-NG. Only the vtable order and by-value struct layouts must match
// the original, so every virtual is kept in its exact original slot with an
// ABI-compatible signature (legacy type names mapped to their RE:: equivalents).
//
// Reference: https://github.com/adamhynek/higgs  include/higgsinterface001.h

#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"

namespace HiggsAPI {
    struct IHiggsInterface001 {
        virtual std::uint32_t GetBuildNumber() = 0;

        using PulledCallback = void (*)(bool isLeft, RE::TESObjectREFR* pulledRefr);
        virtual void AddPulledCallback(PulledCallback callback) = 0;

        using GrabbedCallback = void (*)(bool isLeft, RE::TESObjectREFR* grabbedRefr);
        virtual void AddGrabbedCallback(GrabbedCallback callback) = 0;

        using DroppedCallback = void (*)(bool isLeft, RE::TESObjectREFR* droppedRefr);
        virtual void AddDroppedCallback(DroppedCallback callback) = 0;

        using StashedCallback = void (*)(bool isLeft, RE::TESForm* stashedForm);
        virtual void AddStashedCallback(StashedCallback callback) = 0;

        using ConsumedCallback = void (*)(bool isLeft, RE::TESForm* consumedForm);
        virtual void AddConsumedCallback(ConsumedCallback callback) = 0;

        // Fires when a hand or held object collides with something.
        using CollisionCallback = void (*)(bool isLeft, float mass, float separatingVelocity);
        virtual void AddCollisionCallback(CollisionCallback callback) = 0;

        virtual void GrabObject(RE::TESObjectREFR* object, bool isLeft) = 0;
        virtual RE::TESObjectREFR* GetGrabbedObject(bool isLeft) = 0;
        virtual bool IsHandInGrabbableState(bool isLeft) = 0;
        virtual void DisableHand(bool isLeft) = 0;
        virtual void EnableHand(bool isLeft) = 0;
        virtual bool IsDisabled(bool isLeft) = 0;
        virtual void DisableWeaponCollision(bool isLeft) = 0;
        virtual void EnableWeaponCollision(bool isLeft) = 0;
        virtual bool IsWeaponCollisionDisabled(bool isLeft) = 0;
        virtual bool IsTwoHanding() = 0;

        using StartTwoHandingCallback = void (*)();
        virtual void AddStartTwoHandingCallback(StartTwoHandingCallback callback) = 0;
        using StopTwoHandingCallback = void (*)();
        virtual void AddStopTwoHandingCallback(StopTwoHandingCallback callback) = 0;

        virtual bool CanGrabObject(bool isLeft) = 0;

        enum class CollisionFilterComparisonResult : std::uint8_t {
            Continue,  // do not affect whether the two objects should collide
            Collide,   // force the two objects to collide
            Ignore,    // force the two objects to not collide
        };
        // collisionFilter is really bhkCollisionFilter*. Called hundreds of times per frame.
        using CollisionFilterComparisonCallback =
            CollisionFilterComparisonResult (*)(void* collisionFilter, std::uint32_t filterInfoA, std::uint32_t filterInfoB);
        virtual void AddCollisionFilterComparisonCallback(CollisionFilterComparisonCallback callback) = 0;

        // Called right before hkpWorld::stepDeltaTime. world is really bhkWorld*.
        using PrePhysicsStepCallback = void (*)(void* world);
        virtual void AddPrePhysicsStepCallback(PrePhysicsStepCallback callback) = 0;

        virtual std::uint64_t GetHiggsLayerBitfield() = 0;
        virtual void SetHiggsLayerBitfield(std::uint64_t bitfield) = 0;

        // All three return bhkRigidBody* (typed as NiObject* in the original).
        virtual RE::NiObject* GetHandRigidBody(bool isLeft) = 0;
        virtual RE::NiObject* GetWeaponRigidBody(bool isLeft) = 0;
        virtual RE::NiObject* GetGrabbedRigidBody(bool isLeft) = 0;

        virtual void ForceWeaponCollisionEnabled(bool isLeft) = 0;
        virtual bool IsHoldingObject(bool isLeft) = 0;
        virtual void GetFingerValues(bool isLeft, float values[5]) = 0;

        using NoArgCallback = void (*)();
        virtual void AddPreVrikPreHiggsCallback(NoArgCallback callback) = 0;
        virtual void AddPreVrikPostHiggsCallback(NoArgCallback callback) = 0;
        virtual void AddPostVrikPreHiggsCallback(NoArgCallback callback) = 0;
        virtual void AddPostVrikPostHiggsCallback(NoArgCallback callback) = 0;

        virtual bool Deprecated1(const std::string_view& name, double& out) = 0;
        virtual bool Deprecated2(const std::string& name, double val) = 0;

        virtual RE::NiTransform GetGrabTransform(bool isLeft) = 0;
        virtual void SetGrabTransform(bool isLeft, const RE::NiTransform& transform) = 0;

        virtual bool GetSettingDouble(const char* name, double& out) = 0;
        virtual bool SetSettingDouble(const char* name, double val) = 0;

        virtual RE::BSFixedString GetGrabbedNodeName(bool isLeft) = 0;
    };

    inline IHiggsInterface001* g_higgs = nullptr;

    // Fetch HIGGS's interface. Safe to call once HIGGS has processed SKSE kPostLoad,
    // i.e. from our plugin's kPostLoad handler or later.
    inline IHiggsInterface001* GetHiggsInterface() {
        if (g_higgs) {
            return g_higgs;
        }
        auto* messaging = SKSE::GetMessagingInterface();
        if (!messaging) {
            return nullptr;
        }
        struct HiggsMessage {
            enum { kMessage_GetInterface = 0xF9279A57 };
            void* (*GetApiFunction)(unsigned int revisionNumber) = nullptr;
        } msg;
        messaging->Dispatch(HiggsMessage::kMessage_GetInterface, &msg, sizeof(void*), "HIGGS");
        if (!msg.GetApiFunction) {
            return nullptr;
        }
        g_higgs = static_cast<IHiggsInterface001*>(msg.GetApiFunction(1));
        return g_higgs;
    }
}
