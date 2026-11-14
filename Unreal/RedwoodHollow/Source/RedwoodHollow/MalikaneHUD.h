#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MalikaneHUD.generated.h"

/**
 * Draws the interaction prompt: a white circle with the key letter, anchored over the gap in the
 * world, and a green ring around it that fills while the key is held.
 */
UCLASS()
class REDWOODHOLLOW_API AMalikaneHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

	UPROPERTY(EditAnywhere, Category = "Etkilesim")
	float Radius = 30.f;

private:
	/** Filled ring between two radii from angle 0 (12 o'clock) clockwise over Fraction of a turn. */
	void DrawRing(const FVector2D& Center, float Inner, float Outer, float Fraction, const FLinearColor& Color);
};
