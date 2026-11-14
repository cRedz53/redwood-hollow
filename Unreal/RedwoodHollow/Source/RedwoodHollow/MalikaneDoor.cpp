#include "MalikaneDoor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"

AMalikaneDoor::AMalikaneDoor()
{
	PrimaryActorTick.bCanEverTick = true;

	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	Hinge->SetMobility(EComponentMobility::Movable);
	RootComponent = Hinge;

	Leaf = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Leaf"));
	Leaf->SetupAttachment(Hinge);
	Leaf->SetMobility(EComponentMobility::Movable);
	Leaf->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
}

void AMalikaneDoor::BeginPlay()
{
	Super::BeginPlay();
	Alpha = bOpen ? 1.f : 0.f;
	ApplyAlpha();
}

void AMalikaneDoor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Alpha = bOpen ? 1.f : 0.f;
	ApplyAlpha();
}

void AMalikaneDoor::Toggle()
{
	if (bLocked)
	{
		return;
	}
	SetOpen(!bOpen);
	if (Partner && Partner->bOpen != bOpen)
	{
		Partner->SetOpen(bOpen);
	}
}

void AMalikaneDoor::SetOpen(bool bNewOpen)
{
	bOpen = bNewOpen;
}

void AMalikaneDoor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float Target = bOpen ? 1.f : 0.f;
	if (!FMath::IsNearlyEqual(Alpha, Target))
	{
		Alpha = FMath::FInterpConstantTo(Alpha, Target, DeltaSeconds, Speed);
		ApplyAlpha();
	}
}

void AMalikaneDoor::ApplyAlpha()
{
	// ease in/out so heavy doors start and stop softly
	const float Eased = 0.5f - 0.5f * FMath::Cos(Alpha * PI);
	const float Angle = OpenAngle * Eased;
	Leaf->SetRelativeRotation(bHorizontal ? FRotator(0.f, 0.f, Angle) : FRotator(0.f, Angle, 0.f));
}
