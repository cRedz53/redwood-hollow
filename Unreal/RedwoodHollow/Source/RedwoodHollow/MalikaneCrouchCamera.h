#pragma once

#include "CoreMinimal.h"
#include "Camera/CameraModifier.h"
#include "MalikaneCrouchCamera.generated.h"

/**
 * Crouching shrinks the capsule instantly, which would make the third-person camera jump down.
 * This modifier eases the camera height towards wherever the character's camera wants to be.
 */
UCLASS()
class REDWOODHOLLOW_API UMalikaneCrouchCamera : public UCameraModifier
{
	GENERATED_BODY()

public:
	/** How quickly the camera height follows (higher = snappier). */
	UPROPERTY(EditAnywhere, Category = "Egilme")
	float Speed = 8.f;

	virtual bool ModifyCamera(float DeltaTime, FMinimalViewInfo& InOutPOV) override;

private:
	float Height = -1.f;  // smoothed camera height above the floor
};
