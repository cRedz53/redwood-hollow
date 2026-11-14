using UnrealBuildTool;

public class RedwoodHollowEditorTarget : TargetRules
{
	public RedwoodHollowEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("RedwoodHollow");
	}
}
