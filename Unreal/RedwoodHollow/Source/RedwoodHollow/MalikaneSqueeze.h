#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MalikaneSqueeze.generated.h"

class AMalikaneDoor;
class APlayerController;

/**
 * A gap too narrow to walk through (e.g. between a wardrobe and an open door). Standing near either end
 * and pressing E plays a "squeeze through sideways" move: the player turns side-on, slides across with
 * a slow shuffle and a slight camera tilt, then turns back. Collision is off while squeezing.
 */
UCLASS()
class REDWOODHOLLOW_API AMalikaneSqueeze : public AActor
{
	GENERATED_BODY()

public:
	AMalikaneSqueeze();

	/** Ends of the gap in world space; the player may start from either. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gecit")
	FVector PointA = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gecit")
	FVector PointB = FVector::ZeroVector;

	/** The gap only opens up while this door is open (optional). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gecit")
	TObjectPtr<AMalikaneDoor> RequiredDoor;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gecit")
	float Duration = 3.2f;

	/** How close (cm, horizontally) to an end the player must be to start. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gecit")
	float UseRadius = 130.f;

	/** True when the pawn is next to an end, the door is open and nobody is squeezing. */
	bool CanUse(const APawn* Pawn) const;

	void Begin(APlayerController* PC);

	virtual void Tick(float DeltaSeconds) override;

private:
	TWeakObjectPtr<APlayerController> User;
	FVector From = FVector::ZeroVector;
	FVector To = FVector::ZeroVector;
	FRotator StartView = FRotator::ZeroRotator;
	float Alpha = -1.f;

	void Finish();
};
