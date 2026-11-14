#include "MalikaneInteractor.h"

#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "MalikaneDoor.h"

AMalikaneInteractor::AMalikaneInteractor()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AMalikaneInteractor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bBound)
	{
		TryBind();  // the player controller may not exist yet on the first frames
	}
}

void AMalikaneInteractor::TryBind()
{
	APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (!PC)
	{
		return;
	}
	EnableInput(PC);
	if (InputComponent)
	{
		InputComponent->bBlockInput = false;
		FInputKeyBinding& Binding = InputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &AMalikaneInteractor::OnClick);
		Binding.bConsumeInput = false;  // leave the click for anything else that wants it
		bBound = true;
	}
}

void AMalikaneInteractor::OnClick()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC)
	{
		return;
	}
	FVector Eye;
	FRotator View;
	PC->GetPlayerViewPoint(Eye, View);

	FCollisionQueryParams Params(SCENE_QUERY_STAT(MalikaneInteract), true);
	if (APawn* Pawn = PC->GetPawn())
	{
		Params.AddIgnoredActor(Pawn);
	}
	FHitResult Hit;
	if (GetWorld()->LineTraceSingleByChannel(Hit, Eye, Eye + View.Vector() * InteractRange, ECC_Visibility, Params))
	{
		if (AMalikaneDoor* Door = Cast<AMalikaneDoor>(Hit.GetActor()))
		{
			Door->Toggle();
		}
	}
}

void AMalikaneInteractor::KapilariDegistir()
{
	for (TActorIterator<AMalikaneDoor> It(GetWorld()); It; ++It)
	{
		if (!It->bLocked)
		{
			It->SetOpen(!It->bOpen);
		}
	}
}
