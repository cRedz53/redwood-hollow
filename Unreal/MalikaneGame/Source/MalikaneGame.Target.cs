using UnrealBuildTool;

public class MalikaneGameTarget : TargetRules
{
	public MalikaneGameTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("MalikaneGame");
	}
}
