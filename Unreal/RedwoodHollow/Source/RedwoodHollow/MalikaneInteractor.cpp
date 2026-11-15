#include "MalikaneInteractor.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/BlendSpace.h"
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
	UpdateCrouchAnimation(DeltaSeconds);
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

void AMalikaneInteractor::PlayOverride(USkeletalMeshComponent* Mesh, UAnimationAsset* Clip, bool bLoop)
{
	if (!Clip || Clip == PlayingOverride)
	{
		return;
	}
	if (!PlayingOverride)
	{
		NormalAnimClass = Mesh->GetAnimClass();  // remember the blueprint to hand back to
	}
	Mesh->PlayAnimation(Clip, bLoop);
	PlayingOverride = Clip;
	StateTime = 0.f;
}

void AMalikaneInteractor::RestoreAnimBlueprint(USkeletalMeshComponent* Mesh)
{
	if (!PlayingOverride)
	{
		return;
	}
	Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	if (NormalAnimClass)
	{
		Mesh->SetAnimInstanceClass(NormalAnimClass);
	}
	Mesh->SetPlayRate(1.f);
	PlayingOverride = nullptr;
}

void AMalikaneInteractor::UpdateCrouchAnimation(float DeltaSeconds)
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr;
	USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
	if (!Mesh)
	{
		return;
	}
	if (!CrouchBlend)
	{
		const TCHAR* Dir = TEXT("/Game/Characters/Mannequins/Anims/Crouch/");
		auto Path = [Dir](const TCHAR* Name) { return FString::Printf(TEXT("%s%s.%s"), Dir, Name, Name); };
		CrouchEntry = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Entry")));
		CrouchExit = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Exit")));
		CrouchBlend = LoadObject<UBlendSpace>(nullptr, *Path(TEXT("BS_MM_CrouchStrafe")));
		SideStep = LoadObject<UAnimSequence>(nullptr,
			TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Right.MF_Unarmed_Walk_Right"));
		if (!SideStep)  // folder layout differs between template versions
		{
			SideStep = LoadObject<UAnimSequence>(nullptr,
				TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MF_Unarmed_Walk_Right.MF_Unarmed_Walk_Right"));
		}
	}
	StateTime += DeltaSeconds;
	const FVector Velocity = Character->GetVelocity();
	const float Speed = Velocity.Size2D();
	const bool bCrouched = Character->bIsCrouched;
	bool bSqueezing = false;
	for (TActorIterator<AMalikaneSqueeze> It(GetWorld()); It; ++It)
	{
		bSqueezing |= It->IsBusy();
	}
	auto Length = [](const UAnimSequence* Clip) { return Clip ? Clip->GetPlayLength() : 0.f; };

	// state machine: Normal -> Entering (crouch down) -> Crouched (blend space) -> Exiting (stand up) -> Normal
	if (bSqueezing)
	{
		AnimState = ECrouchAnim::Squeezing;
		PlayOverride(Mesh, SideStep, true);  // upright side-step, slowed to a shuffle
		Mesh->SetPlayRate(0.55f);
		return;
	}
	switch (AnimState)
	{
	case ECrouchAnim::Squeezing:
		if (bCrouched)
		{
			AnimState = ECrouchAnim::Crouched;
		}
		else
		{
			AnimState = ECrouchAnim::Normal;
			RestoreAnimBlueprint(Mesh);
		}
		break;
	case ECrouchAnim::Normal:
		if (bCrouched)
		{
			AnimState = ECrouchAnim::Entering;
			PlayOverride(Mesh, CrouchEntry, false);
		}
		break;
	case ECrouchAnim::Entering:
		if (!bCrouched)
		{
			AnimState = ECrouchAnim::Exiting;
			PlayOverride(Mesh, CrouchExit, false);
		}
		else if (StateTime >= Length(CrouchEntry) || Speed > 15.f)
		{
			AnimState = ECrouchAnim::Crouched;  // down (or already moving): hand over to the blend space
			BlendSpeed = 0.f;
		}
		break;
	case ECrouchAnim::Crouched:
		if (!bCrouched)
		{
			AnimState = ECrouchAnim::Exiting;
			PlayOverride(Mesh, CrouchExit, false);
		}
		break;
	case ECrouchAnim::Exiting:
		if (bCrouched)
		{
			AnimState = ECrouchAnim::Crouched;
		}
		else if (StateTime >= Length(CrouchExit) || Speed > 15.f)
		{
			AnimState = ECrouchAnim::Normal;
			RestoreAnimBlueprint(Mesh);
		}
		break;
	}
	if (AnimState == ECrouchAnim::Crouched)
	{
		PlayOverride(Mesh, CrouchBlend, true);
		// the blend space mixes idle (speed 0) into the walks (speed 100), so starting and stopping
		// ease in and out instead of snapping between two clips
		BlendSpeed = FMath::FInterpTo(BlendSpeed, FMath::Min(Speed, 100.f), DeltaSeconds, 6.f);
		float Direction = 0.f;
		if (Speed > 5.f)
		{
			const FRotator Facing = Character->GetActorRotation();
			Direction = FMath::FindDeltaAngleDegrees(Facing.Yaw, Velocity.Rotation().Yaw);
		}
		if (UAnimSingleNodeInstance* Single = Mesh->GetSingleNodeInstance())
		{
			Single->SetBlendSpacePosition(FVector(Direction, BlendSpeed, 0.f));
		}
		Mesh->SetPlayRate(FMath::Clamp(Speed / 100.f, 1.f, 1.3f));  // only speeds up past the clip's own pace
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
	AMalikaneDoor* Door = nullptr;
	if (GetWorld()->LineTraceSingleByChannel(Hit, Eye, Eye + View.Vector() * InteractRange, ECC_Visibility, Params))
	{
		Door = Cast<AMalikaneDoor>(Hit.GetActor());
	}
	if (!Door)
	{
		// the over-the-shoulder trace can be blocked by furniture standing half in front of a door
		Door = FindDoorInFront(Eye, View.Vector());
	}
	if (Door)
	{
		Door->Toggle();
	}
}

AMalikaneDoor* AMalikaneInteractor::FindDoorInFront(const FVector& Eye, const FVector& ViewDir) const
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return nullptr;
	}
	const FVector P = Pawn->GetActorLocation();
	const FVector Look = ViewDir.GetSafeNormal2D();
	AMalikaneDoor* Best = nullptr;
	float BestScore = 0.f;
	for (TActorIterator<AMalikaneDoor> It(GetWorld()); It; ++It)
	{
		const FVector Center = It->Leaf->Bounds.Origin;
		const FVector To = Center - P;
		const float Dist = To.Size2D();
		if (Dist > 200.f || FMath::Abs(To.Z) > 250.f)
		{
			continue;
		}
		const float Facing = FVector::DotProduct(To.GetSafeNormal2D(), Look);
		if (Facing < 0.5f)  // within ~60 degrees of where the camera points
		{
			continue;
		}
		const float Score = Facing / FMath::Max(Dist, 30.f);
		if (Score > BestScore)
		{
			BestScore = Score;
			Best = *It;
		}
	}
	return Best;
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
