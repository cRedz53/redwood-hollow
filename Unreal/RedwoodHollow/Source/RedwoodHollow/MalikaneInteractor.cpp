#include "MalikaneInteractor.h"

#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "MalikaneCrouchCamera.h"
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
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (Pawn && CameraPawn.Get() != Pawn)
	{
		SetupCamera(Pawn);  // again after a respawn
	}
	UpdateCrouchAnimation();
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
		for (const FKey& Key : {EKeys::LeftControl, EKeys::RightControl})
		{
			InputComponent->BindKey(Key, IE_Pressed, this, &AMalikaneInteractor::OnCrouchPressed).bConsumeInput = false;
			InputComponent->BindKey(Key, IE_Released, this, &AMalikaneInteractor::OnCrouchReleased).bConsumeInput = false;
		}
		PC->ClientSetHUD(AMalikaneHUD::StaticClass());
		if (PC->PlayerCameraManager)
		{
			PC->PlayerCameraManager->AddNewCameraModifier(UMalikaneCrouchCamera::StaticClass());
		}
		bBound = true;
	}
}

void AMalikaneInteractor::SetupCamera(APawn* Pawn)
{
	CameraPawn = Pawn;
	if (USpringArmComponent* Boom = Pawn->FindComponentByClass<USpringArmComponent>())
	{
		// close over-the-shoulder view: right shoulder, slightly above the head, a touch of lag
		Boom->TargetArmLength = CameraDistance;
		Boom->SocketOffset = CameraOffset;
		Boom->bEnableCameraLag = true;
		Boom->CameraLagSpeed = 14.f;
		Boom->ProbeSize = 14.f;
	}
	if (UCameraComponent* Camera = Pawn->FindComponentByClass<UCameraComponent>())
	{
		Camera->SetFieldOfView(80.f);
	}
}

void AMalikaneInteractor::UpdateCrouchAnimation()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr;
	USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
	if (!Mesh)
	{
		return;
	}
	if (!CrouchIdle)
	{
		CrouchIdle = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Unarmed_Crouch_Idle.MM_Unarmed_Crouch_Idle"));
		CrouchWalk = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Unarmed_Crouch_Walk_Fwd.MM_Unarmed_Crouch_Walk_Fwd"));
		CrouchStrafe = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Unarmed_Crouch_Walk_Right.MM_Unarmed_Crouch_Walk_Right"));
	}
	bool bSqueezing = false;
	for (TActorIterator<AMalikaneSqueeze> It(GetWorld()); It; ++It)
	{
		bSqueezing |= It->IsBusy();
	}

	// pick the clip: shuffle sideways in a gap, crouch walk / idle while crouched, else the anim blueprint
	UAnimSequence* Wanted = nullptr;
	const float Speed = Character->GetVelocity().Size2D();
	if (bSqueezing)
	{
		Wanted = CrouchStrafe;
	}
	else if (Character->bIsCrouched)
	{
		Wanted = Speed > 15.f ? CrouchWalk : CrouchIdle;
	}

	if (Wanted && Wanted != PlayingOverride)
	{
		if (!PlayingOverride)
		{
			NormalAnimClass = Mesh->GetAnimClass();
		}
		Mesh->PlayAnimation(Wanted, true);
		PlayingOverride = Wanted;
	}
	else if (!Wanted && PlayingOverride)
	{
		Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
		if (NormalAnimClass)
		{
			Mesh->SetAnimInstanceClass(NormalAnimClass);
		}
		PlayingOverride = nullptr;
	}
	if (PlayingOverride == CrouchWalk)
	{
		Mesh->SetPlayRate(FMath::Clamp(Speed / 150.f, 0.6f, 1.5f));  // keep the feet from sliding
	}
	else if (PlayingOverride)
	{
		Mesh->SetPlayRate(1.f);
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

void AMalikaneInteractor::OnCrouchPressed()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr)
	{
		UCharacterMovementComponent* Move = Character->GetCharacterMovement();
		Move->GetNavAgentPropertiesRef().bCanCrouch = true;
		Move->SetCrouchedHalfHeight(CrouchedHalfHeight);
		Move->MaxWalkSpeedCrouched = CrouchSpeed;
		Character->Crouch();
	}
}

void AMalikaneInteractor::OnCrouchReleased()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr)
	{
		Character->UnCrouch();  // movement keeps retrying until there is head room (e.g. under a table)
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
