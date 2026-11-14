using UnrealBuildTool;

public class RedwoodHollowTarget : TargetRules
{
	public RedwoodHollowTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("RedwoodHollow");
	}
}
