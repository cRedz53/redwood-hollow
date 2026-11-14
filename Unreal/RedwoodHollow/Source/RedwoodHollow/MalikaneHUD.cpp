#include "MalikaneHUD.h"

#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "MalikaneInteractor.h"
#include "MalikaneSqueeze.h"

void AMalikaneHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	AMalikaneInteractor* Interactor = nullptr;
	for (TActorIterator<AMalikaneInteractor> It(GetWorld()); It; ++It)
	{
		Interactor = *It;
		break;
	}
	float Progress = 0.f;
	AMalikaneSqueeze* Gap = Interactor ? Interactor->GetUsableGap(Progress) : nullptr;
	if (!Gap)
	{
		return;
	}
	// anchor the prompt over the middle of the gap, at about eye height
	const FVector World = Gap->GetPromptLocation();
	const FVector Screen = Project(World, true);
	if (Screen.Z <= 0.f)
	{
		return;  // behind the camera
	}
	const FVector2D C(Screen.X, Screen.Y);
	const float R = Radius * FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.f);

	DrawRing(C, 0.f, R, 1.f, FLinearColor(0.f, 0.f, 0.f, 0.45f));                 // dark backing for contrast
	DrawRing(C, R * 0.86f, R, 1.f, FLinearColor::White);                           // white circle
	DrawRing(C, R * 1.08f, R * 1.32f, 1.f, FLinearColor(0.f, 0.f, 0.f, 0.35f));    // empty track
	if (Progress > 0.f)
	{
		DrawRing(C, R * 1.08f, R * 1.32f, Progress, FLinearColor(0.15f, 0.85f, 0.3f, 1.f));  // green fill
	}

	UFont* Font = GEngine->GetLargeFont();
	const float Scale = R / 22.f;
	float W, H;
	Canvas->TextSize(Font, TEXT("E"), W, H, Scale, Scale);
	FCanvasTextItem Letter(FVector2D(C.X - W / 2.f, C.Y - H / 2.f), FText::FromString(TEXT("E")), Font, FLinearColor::White);
	Letter.Scale = FVector2D(Scale, Scale);
	Canvas->DrawItem(Letter);
}

void AMalikaneHUD::DrawRing(const FVector2D& Center, float Inner, float Outer, float Fraction, const FLinearColor& Color)
{
	const int32 Segments = FMath::Max(3, FMath::CeilToInt(64 * Fraction));
	TArray<FCanvasUVTri> Tris;
	Tris.Reserve(Segments * 2);
	auto Point = [&Center](float Radius, float Angle)
	{
		// angle 0 at 12 o'clock, growing clockwise on screen (y points down)
		return FVector2D(Center.X + Radius * FMath::Sin(Angle), Center.Y - Radius * FMath::Cos(Angle));
	};
	for (int32 i = 0; i < Segments; ++i)
	{
		const float A0 = 2.f * PI * Fraction * i / Segments;
		const float A1 = 2.f * PI * Fraction * (i + 1) / Segments;
		const FVector2D O0 = Point(Outer, A0), O1 = Point(Outer, A1);
		const FVector2D I0 = Point(Inner, A0), I1 = Point(Inner, A1);
		FCanvasUVTri T;
		T.V0_Color = T.V1_Color = T.V2_Color = Color;
		T.V0_Pos = O0; T.V1_Pos = O1; T.V2_Pos = I1;
		Tris.Add(T);
		if (Inner > 0.f)
		{
			T.V0_Pos = O0; T.V1_Pos = I1; T.V2_Pos = I0;
			Tris.Add(T);
		}
	}
	FCanvasTriangleItem Item(Tris, GWhiteTexture);
	Item.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Item);
}
