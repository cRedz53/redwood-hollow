param([string]$Out = (Join-Path $PSScriptRoot "..\Gorseller\ue_oyun_ici.png"), [int]$Wait = 50)
# Oyunu -game modunda acar, bekler, oyun penceresinin goruntusunu alir ve kapatir.
#   powershell -ExecutionPolicy Bypass -File Araclar\oyun_ekran_goruntusu.ps1
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Ri, B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
$proj = (Resolve-Path (Join-Path $PSScriptRoot "..\Unreal\RedwoodHollow\RedwoodHollow.uproject")).Path
$exe = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$p = Start-Process -FilePath $exe -ArgumentList "`"$proj`"", "-game", "-windowed", "-ResX=1600", "-ResY=900", "-nosplash" -PassThru
Start-Sleep -Seconds $Wait
$p.Refresh()
$h = $p.MainWindowHandle
[W]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Seconds 3
$r = New-Object W+R
[W]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Ri - $r.L; $hgt = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap $w, $hgt
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Stop-Process -Id $p.Id -Force
"saved $Out ${w}x$hgt"
