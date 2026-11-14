#include "MalikaneCrouchCamera.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"

bool UMalikaneCrouchCamera::ModifyCamera(float DeltaTime, FMinimalViewInfo& InOutPOV)
{
	Super::ModifyCamera(DeltaTime, InOutPOV);

	APlayerController* PC = CameraOwner ? CameraOwner->GetOwningPlayerController() : nullptr;
	ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr;
	if (!Character)
	{
		return false;
	}
	// capsule bottom stays put while crouching, so it is a stable floor reference
	const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
	const float Floor = Capsule->GetComponentLocation().Z - Capsule->GetScaledCapsuleHalfHeight();
	const float Natural = InOutPOV.Location.Z - Floor;
	const float Target = Character->bIsCrouched ? FMath::Min(CrouchedEyeHeight, Natural) : Natural;

	EyeHeight = EyeHeight < 0.f ? Natural : FMath::FInterpTo(EyeHeight, Target, DeltaTime, Speed);
	if (!Character->bIsCrouched && FMath::IsNearlyEqual(EyeHeight, Natural, 0.5f))
	{
		EyeHeight = Natural;  // standing and settled: leave the camera exactly as the character made it
	}
	InOutPOV.Location.Z = Floor + EyeHeight;
	return false;
}
