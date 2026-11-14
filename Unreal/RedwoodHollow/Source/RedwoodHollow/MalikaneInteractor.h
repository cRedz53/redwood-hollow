#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MalikaneInteractor.generated.h"

class AMalikaneDoor;
class AMalikaneSqueeze;
class UAnimSequence;
class USkeletalMeshComponent;

/**
 * Placed once in the level. Listens for the left mouse button on the first player controller,
 * traces from the camera and toggles the door the player is looking at. Holding E for HoldDuration
 * seconds at a narrow gap (AMalikaneSqueeze) squeezes through it; AMalikaneHUD draws the prompt.
 * Holding Ctrl crouches; while crouched (or squeezing) the third-person mesh plays the crouch
 * animations instead of its animation blueprint. Also sets up the over-the-shoulder camera.
 */
UCLASS()
class REDWOODHOLLOW_API AMalikaneInteractor : public AActor
{
	GENERATED_BODY()

public:
	AMalikaneInteractor();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Etkilesim")
	float InteractRange = 450.f;

	/** Seconds E must be held at a gap before squeezing through. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Etkilesim")
	float HoldDuration = 0.7f;

	/** Crouched capsule half height (cm); the mansion tables leave ~118 cm underneath. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Egilme")
	float CrouchedHalfHeight = 55.f;

	/** Crouched walking speed (cm/s); the crouch-walk clip is played at a rate matched to it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Egilme")
	float CrouchSpeed = 140.f;

	/** Speed (cm/s) at which the crouch-walk clip's feet don't slide at play rate 1. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Egilme")
	float CrouchWalkClipSpeed = 140.f;

	/** Over-the-shoulder camera: boom length and offset to the right / up (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kamera")
	float CameraDistance = 230.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kamera")
	FVector CameraOffset = FVector(0.f, 55.f, 45.f);

	/** Toggles every door in the level (debug / testing: `ke * KapilariDegistir`). */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Etkilesim")
	void KapilariDegistir();

	/** The gap the player can use right now (nullptr if none) and how far the E hold has filled (0-1). */
	AMalikaneSqueeze* GetUsableGap(float& OutProgress) const;

	virtual void Tick(float DeltaSeconds) override;

private:
	bool bBound = false;
	bool bHoldingUse = false;
	float HoldTime = 0.f;
	TWeakObjectPtr<APawn> CameraPawn;  // pawn whose camera boom has been set up

	/** What the mesh is doing instead of its animation blueprint. */
	enum class ECrouchAnim : uint8 { Normal, Entering, Crouched, Exiting, Squeezing };
	ECrouchAnim AnimState = ECrouchAnim::Normal;
	float StateTime = 0.f;

	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> CrouchEntry;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> CrouchExit;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> CrouchIdle;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> CrouchWalk;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> CrouchStrafe;
	UPROPERTY(Transient)
	TObjectPtr<UClass> NormalAnimClass;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> PlayingOverride;

	void TryBind();
	void SetupCamera(APawn* Pawn);
	void UpdateCrouchAnimation(float DeltaSeconds);
	void PlayOverride(USkeletalMeshComponent* Mesh, UAnimSequence* Clip, bool bLoop);
	void RestoreAnimBlueprint(USkeletalMeshComponent* Mesh);
	/** A door near the pawn in the view direction, for when the trace is blocked by furniture. */
	AMalikaneDoor* FindDoorInFront(const FVector& Eye, const FVector& ViewDir) const;
	void OnClick();
	void OnUsePressed();
	void OnUseReleased();
	void OnCrouchPressed();
	void OnCrouchReleased();
};
