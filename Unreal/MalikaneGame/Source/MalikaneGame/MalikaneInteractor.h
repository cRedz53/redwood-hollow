#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MalikaneInteractor.generated.h"

/**
 * Placed once in the level. Listens for the left mouse button on the first player controller,
 * traces from the camera and toggles the door the player is looking at.
 */
UCLASS()
class MALIKANEGAME_API AMalikaneInteractor : public AActor
{
	GENERATED_BODY()

public:
	AMalikaneInteractor();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Etkilesim")
	float InteractRange = 350.f;

	/** Toggles every door in the level (debug / testing: `ke * KapilariDegistir`). */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Etkilesim")
	void KapilariDegistir();

	virtual void Tick(float DeltaSeconds) override;

private:
	bool bBound = false;
	void TryBind();
	void OnClick();
};
