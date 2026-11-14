using UnrealBuildTool;

public class MalikaneGameEditorTarget : TargetRules
{
	public MalikaneGameEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("MalikaneGame");
	}
}
