#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MalikaneDoor.generated.h"

class UStaticMeshComponent;

/** A door leaf that swings around its hinge (the actor origin). Double doors point at each other via Partner. */
UCLASS()
class REDWOODHOLLOW_API AMalikaneDoor : public AActor
{
	GENERATED_BODY()

public:
	AMalikaneDoor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Kapi")
	TObjectPtr<USceneComponent> Hinge;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Kapi")
	TObjectPtr<UStaticMeshComponent> Leaf;

	/** Yaw (degrees) the leaf turns to when fully open; the sign picks the swing side. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	float OpenAngle = 90.f;

	/** Full open/close cycles per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	float Speed = 1.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	bool bOpen = false;

	/** Locked doors ignore Toggle (e.g. the escape gate until the player finds the key). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	bool bLocked = false;

	/** Floor hatch: the leaf lies flat and swings up around its hinge edge (roll) instead of turning around Z. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	bool bHorizontal = false;

	/** The other leaf of a double door; it opens and closes together with this one. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kapi")
	TObjectPtr<AMalikaneDoor> Partner;

	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Kapi")
	void Toggle();

	UFUNCTION(BlueprintCallable, Category = "Kapi")
	void SetOpen(bool bNewOpen);

	virtual void Tick(float DeltaSeconds) override;

	/** Shows the open/closed pose in the editor too. */
	virtual void OnConstruction(const FTransform& Transform) override;

protected:
	virtual void BeginPlay() override;

private:
	float Alpha = 0.f;
	void ApplyAlpha();
};
