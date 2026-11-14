#pragma once

#include "CoreMinimal.h"
#include "Camera/CameraModifier.h"
#include "MalikaneCrouchCamera.generated.h"

/**
 * Smoothly lowers the view while the character is crouched, so the eye ends up low enough to look
 * around under tables. Works on the final camera position, whatever the camera is attached to.
 */
UCLASS()
class REDWOODHOLLOW_API UMalikaneCrouchCamera : public UCameraModifier
{
	GENERATED_BODY()

public:
	/** Eye height above the floor while crouched (cm). */
	UPROPERTY(EditAnywhere, Category = "Egilme")
	float CrouchedEyeHeight = 55.f;

	/** How quickly the eye follows (higher = snappier). */
	UPROPERTY(EditAnywhere, Category = "Egilme")
	float Speed = 9.f;

	virtual bool ModifyCamera(float DeltaTime, FMinimalViewInfo& InOutPOV) override;

private:
	float EyeHeight = -1.f;  // smoothed eye height above the floor
};
