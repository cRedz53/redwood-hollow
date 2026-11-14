#include "MalikaneInteractor.h"

#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "MalikaneDoor.h"
#include "MalikaneHUD.h"
#include "MalikaneSqueeze.h"

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
		return;
	}
	if (!bHoldingUse)
	{
		return;
	}
	float Progress;
	AMalikaneSqueeze* Gap = GetUsableGap(Progress);
	if (!Gap)
	{
		HoldTime = 0.f;  // walked away or the door closed: start over
		return;
	}
	HoldTime += DeltaSeconds;
	if (HoldTime >= HoldDuration)
	{
		Gap->Begin(GetWorld()->GetFirstPlayerController());
		bHoldingUse = false;
		HoldTime = 0.f;
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
		FInputKeyBinding& Click = InputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &AMalikaneInteractor::OnClick);
		Click.bConsumeInput = false;  // leave the click for anything else that wants it
		FInputKeyBinding& UseDown = InputComponent->BindKey(EKeys::E, IE_Pressed, this, &AMalikaneInteractor::OnUsePressed);
		UseDown.bConsumeInput = false;
		FInputKeyBinding& UseUp = InputComponent->BindKey(EKeys::E, IE_Released, this, &AMalikaneInteractor::OnUseReleased);
		UseUp.bConsumeInput = false;
		PC->ClientSetHUD(AMalikaneHUD::StaticClass());
		bBound = true;
	}
}

AMalikaneSqueeze* AMalikaneInteractor::GetUsableGap(float& OutProgress) const
{
	OutProgress = 0.f;
	APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	for (TActorIterator<AMalikaneSqueeze> It(GetWorld()); It; ++It)
	{
		if (It->CanUse(Pawn))
		{
			OutProgress = HoldDuration > 0.f ? FMath::Clamp(HoldTime / HoldDuration, 0.f, 1.f) : 1.f;
			return *It;
		}
	}
	return nullptr;
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

void AMalikaneInteractor::OnUsePressed()
{
	bHoldingUse = true;
	HoldTime = 0.f;
}

void AMalikaneInteractor::OnUseReleased()
{
	bHoldingUse = false;
	HoldTime = 0.f;
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
