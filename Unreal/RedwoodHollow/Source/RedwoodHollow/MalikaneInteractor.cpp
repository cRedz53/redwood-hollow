#include "MalikaneInteractor.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
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

void AMalikaneInteractor::PlaySlot(UAnimInstance* Anim, UAnimSequence* Clip, bool bLoop, float Rate)
{
	if (!Clip)
	{
		return;
	}
	if (Clip == SlotClip && SlotMontage && Anim->Montage_IsPlaying(SlotMontage))
	{
		Anim->Montage_SetPlayRate(SlotMontage, Rate);
		return;
	}
	// a new montage in the same slot group fades the previous one out over its own blend-in time,
	// so every change of clip (and the hand-over from / to locomotion) is a cross-fade
	SlotMontage = Anim->PlaySlotAnimationAsDynamicMontage(Clip, TEXT("DefaultSlot"), CrouchBlendTime, CrouchBlendTime,
		Rate, bLoop ? 100000 : 1);
	SlotClip = Clip;
	StateTime = 0.f;
}

void AMalikaneInteractor::StopSlot(UAnimInstance* Anim, float BlendOut)
{
	if (SlotClip)
	{
		Anim->StopSlotAnimation(BlendOut, TEXT("DefaultSlot"));
	}
	SlotClip = nullptr;
	SlotMontage = nullptr;
}

void AMalikaneInteractor::UpdateCrouchAnimation(float DeltaSeconds)
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ACharacter* Character = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr;
	USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
	UAnimInstance* Anim = Mesh ? Mesh->GetAnimInstance() : nullptr;
	if (!Anim)
	{
		return;
	}
	if (PreparedAnim.Get() != Anim)
	{
		// the crouch-walk and side-step clips carry root motion; the capsule does the moving here,
		// so extract it (keeps the mesh on the capsule) but never apply it
		Anim->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
		PreparedAnim = Anim;
		AnimState = ECrouchAnim::Normal;
		SlotClip = nullptr;
		SlotMontage = nullptr;
	}
	if (!CrouchWalk)
	{
		const TCHAR* Dir = TEXT("/Game/Characters/Mannequins/Anims/Crouch/");
		auto Path = [Dir](const TCHAR* Name) { return FString::Printf(TEXT("%s%s.%s"), Dir, Name, Name); };
		CrouchEntry = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Entry")));
		CrouchExit = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Exit")));
		CrouchIdle = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Idle")));
		CrouchWalk = LoadObject<UAnimSequence>(nullptr, *Path(TEXT("MM_Unarmed_Crouch_Walk_Fwd")));
		SideStep = LoadObject<UAnimSequence>(nullptr,
			TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Right.MF_Unarmed_Walk_Right"));
		if (!SideStep)  // folder layout differs between template versions
		{
			SideStep = LoadObject<UAnimSequence>(nullptr,
				TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MF_Unarmed_Walk_Right.MF_Unarmed_Walk_Right"));
		}
	}
	StateTime += DeltaSeconds;
	const float Speed = Character->GetVelocity().Size2D();
	const bool bCrouched = Character->bIsCrouched;
	bool bSqueezing = false;
	for (TActorIterator<AMalikaneSqueeze> It(GetWorld()); It; ++It)
	{
		bSqueezing |= It->IsBusy();
	}
	auto Length = [](const UAnimSequence* Clip) { return Clip ? Clip->GetPlayLength() : 0.f; };
	const bool bMoving = Speed > 15.f;
	// the template character turns to face where it walks, so the forward crouch walk covers all
	// directions; the play rate keeps the feet in step with the actual speed (no fast shuffling)
	const float WalkRate = FMath::Clamp(Speed / FMath::Max(CrouchWalkClipSpeed, 1.f), 0.45f, 1.1f);

	if (bSqueezing)
	{
		AnimState = ECrouchAnim::Squeezing;
		PlaySlot(Anim, SideStep, true, 0.55f);  // upright side-step, slowed to a shuffle
		return;
	}
	switch (AnimState)
	{
	case ECrouchAnim::Squeezing:
		AnimState = bCrouched ? ECrouchAnim::Crouched : ECrouchAnim::Normal;
		if (!bCrouched)
		{
			StopSlot(Anim, CrouchBlendTime);
		}
		break;
	case ECrouchAnim::Normal:
		if (bCrouched)
		{
			// walking into a crouch goes straight to the crouch walk; standing still crouches down first
			AnimState = bMoving ? ECrouchAnim::Crouched : ECrouchAnim::Entering;
			if (!bMoving)
			{
				PlaySlot(Anim, CrouchEntry, false);
			}
		}
		break;
	case ECrouchAnim::Entering:
		if (!bCrouched)
		{
			AnimState = ECrouchAnim::Exiting;
			PlaySlot(Anim, CrouchExit, false);
		}
		else if (bMoving || StateTime >= Length(CrouchEntry) - CrouchBlendTime)
		{
			AnimState = ECrouchAnim::Crouched;  // fade into the idle / walk loop before the clip ends
		}
		break;
	case ECrouchAnim::Crouched:
		if (!bCrouched)
		{
			if (bMoving)
			{
				AnimState = ECrouchAnim::Normal;  // stand up while walking: fade back into locomotion
				StopSlot(Anim, 0.4f);
			}
			else
			{
				AnimState = ECrouchAnim::Exiting;
				PlaySlot(Anim, CrouchExit, false);
			}
		}
		break;
	case ECrouchAnim::Exiting:
		if (bCrouched)
		{
			AnimState = ECrouchAnim::Crouched;
		}
		else if (bMoving || StateTime >= Length(CrouchExit) - CrouchBlendTime)
		{
			AnimState = ECrouchAnim::Normal;
			StopSlot(Anim, bMoving ? 0.4f : CrouchBlendTime);
		}
		break;
	}
	if (AnimState == ECrouchAnim::Crouched)
	{
		// hysteresis so the idle/walk cross-fade does not flicker around the threshold
		const bool bWalkClip = SlotClip == CrouchWalk;
		if (Speed > 20.f || (bWalkClip && Speed > 6.f))
		{
			PlaySlot(Anim, CrouchWalk, true, WalkRate);
		}
		else
		{
			PlaySlot(Anim, CrouchIdle, true);
		}
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
