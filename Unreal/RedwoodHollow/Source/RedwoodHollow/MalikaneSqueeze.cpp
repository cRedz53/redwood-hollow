#include "MalikaneSqueeze.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "MalikaneDoor.h"

AMalikaneSqueeze::AMalikaneSqueeze()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

bool AMalikaneSqueeze::CanUse(const APawn* Pawn) const
{
	if (!Pawn || Alpha >= 0.f || (RequiredDoor && !RequiredDoor->bOpen))
	{
		return false;
	}
	const FVector P = Pawn->GetActorLocation();
	return FVector::Dist2D(P, PointA) < UseRadius || FVector::Dist2D(P, PointB) < UseRadius;
}

void AMalikaneSqueeze::Begin(APlayerController* PC)
{
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!CanUse(Pawn))
	{
		return;
	}
	const FVector P = Pawn->GetActorLocation();
	const bool bFromA = FVector::Dist2D(P, PointA) <= FVector::Dist2D(P, PointB);
	From = bFromA ? PointA : PointB;
	To = bFromA ? PointB : PointA;
	From.Z = To.Z = P.Z;  // keep the capsule at its current height
	StartView = PC->GetControlRotation();
	User = PC;
	Alpha = 0.f;

	Pawn->SetActorEnableCollision(false);
	if (ACharacter* Character = Cast<ACharacter>(Pawn))
	{
		Character->GetCharacterMovement()->DisableMovement();
	}
	PC->SetIgnoreMoveInput(true);
	PC->SetIgnoreLookInput(true);
}

void AMalikaneSqueeze::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (Alpha < 0.f)
	{
		// prompt while the player stands at an end of the open gap
		if (PC && GEngine && CanUse(PC->GetPawn()))
		{
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(GetUniqueID()), 0.f, FColor(255, 225, 180),
				TEXT("[E] Dar araliktan yan gec"));
		}
		return;
	}

	APawn* Pawn = User.IsValid() ? User->GetPawn() : nullptr;
	if (!Pawn)
	{
		Finish();
		return;
	}
	Alpha = FMath::Min(Alpha + DeltaSeconds / Duration, 1.f);

	// 0-15 %: turn side-on and step to the gap, 15-85 %: shuffle through, 85-100 %: turn back
	const float Slide = FMath::SmoothStep(0.15f, 0.85f, Alpha);
	const float Shuffle = FMath::Sin(Alpha * 9.f * PI);  // small steps
	const FVector Dir = (To - From).GetSafeNormal2D();
	FVector Pos = FMath::Lerp(From, To, Slide);
	Pos.Z += 2.f * FMath::Abs(Shuffle);
	if (Alpha < 0.15f)
	{
		Pos = FMath::Lerp(Pawn->GetActorLocation(), From, Alpha / 0.15f);
	}
	Pawn->SetActorLocation(Pos);

	const float PathYaw = Dir.Rotation().Yaw;
	const float SideYaw = PathYaw + 90.f;  // face the wardrobe / wall while sliding sideways
	float Yaw;
	if (Alpha < 0.15f)
	{
		Yaw = FMath::Lerp(StartView.Yaw, StartView.Yaw + FMath::FindDeltaAngleDegrees(StartView.Yaw, SideYaw), Alpha / 0.15f);
	}
	else if (Alpha < 0.85f)
	{
		Yaw = SideYaw;
	}
	else
	{
		Yaw = FMath::Lerp(SideYaw, SideYaw + FMath::FindDeltaAngleDegrees(SideYaw, PathYaw), (Alpha - 0.85f) / 0.15f);
	}
	const float Squeeze = FMath::Sin(Slide * PI);  // tightest in the middle
	const FRotator View(-6.f * Squeeze, Yaw, 4.f * Squeeze * Shuffle);
	User->SetControlRotation(View);

	if (Alpha >= 1.f)
	{
		Finish();
	}
}

void AMalikaneSqueeze::Finish()
{
	if (APlayerController* PC = User.Get())
	{
		if (APawn* Pawn = PC->GetPawn())
		{
			Pawn->SetActorEnableCollision(true);
			if (ACharacter* Character = Cast<ACharacter>(Pawn))
			{
				Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
			}
		}
		FRotator View = PC->GetControlRotation();
		View.Roll = 0.f;
		PC->SetControlRotation(View);
		PC->ResetIgnoreMoveInput();
		PC->ResetIgnoreLookInput();
	}
	User.Reset();
	Alpha = -1.f;
}
