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
	// the capsule bottom stays put while crouching, so it is a stable floor reference
	const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
	const float Floor = Capsule->GetComponentLocation().Z - Capsule->GetScaledCapsuleHalfHeight();
	const float Wanted = InOutPOV.Location.Z - Floor;
	if (Height < 0.f || FMath::Abs(Wanted - Height) > 300.f)
	{
		Height = Wanted;  // first frame, teleports, stairs falls: no easing
	}
	Height = FMath::FInterpTo(Height, Wanted, DeltaTime, Speed);
	InOutPOV.Location.Z = Floor + Height;
	return false;
}
