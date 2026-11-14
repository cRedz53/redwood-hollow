#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MalikaneInteractor.generated.h"

class AMalikaneSqueeze;

/**
 * Placed once in the level. Listens for the left mouse button on the first player controller,
 * traces from the camera and toggles the door the player is looking at. Holding E for HoldDuration
 * seconds at a narrow gap (AMalikaneSqueeze) squeezes through it; AMalikaneHUD draws the prompt.
 * Holding Ctrl crouches (low enough to hide under tables); UMalikaneCrouchCamera lowers the view.
 */
UCLASS()
class REDWOODHOLLOW_API AMalikaneInteractor : public AActor
{
	GENERATED_BODY()

public:
	AMalikaneInteractor();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Etkilesim")
	float InteractRange = 350.f;

	/** Seconds E must be held at a gap before squeezing through. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Etkilesim")
	float HoldDuration = 0.7f;

	/** Crouched capsule half height (cm): low enough to fit under the mansion tables (~77 cm clearance). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Egilme")
	float CrouchedHalfHeight = 36.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Egilme")
	float CrouchSpeed = 220.f;

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

	void TryBind();
	void OnClick();
	void OnUsePressed();
	void OnUseReleased();
	void OnCrouchPressed();
	void OnCrouchReleased();
};
