param([switch]$SadeceBoyut)
# Poly Haven'dan (CC0, hesap gerektirmez) malikane icin gercekci dokulari ve modelleri indirir.
#   powershell -ExecutionPolicy Bypass -File Araclar\polyhaven_indir.ps1            # indir
#   powershell -ExecutionPolicy Bypass -File Araclar\polyhaven_indir.ps1 -SadeceBoyut  # sadece toplam boyut
# Hedef: Unreal\PolyHaven_Kaynak\  (git'e eklenmez; UE'ye import edilince .uasset olur)

$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot "..\Unreal\PolyHaven_Kaynak"

# yuzey dokulari (2k): ad -> Poly Haven id
$Textures = @(
    "leafy_grass", "gravel_floor_02", "castle_wall_slates", "worn_plaster_wall", "marble_01",
    "roof_slates_02", "weathered_planks", "dark_wood", "herringbone_parquet", "rusty_metal_02", "velour_velvet"
)
# modeller (glTF, 1k dokular)
$Models = @(
    # agaclar, calilar, cim
    # (pine_tree_01 914 MB, fir_tree_01 465 MB: 330 agaclik bahce icin fazla agir)
    "fir_sapling_medium", "island_tree_01", "island_tree_02", "tree_small_02", "dead_tree_trunk_02",
    "shrub_02", "shrub_03", "shrub_04", "fern_02", "grass_medium_01", "grass_medium_02",
    # saray ici
    "Chandelier_01", "Chandelier_03", "GothicBed_01", "GothicCabinet_01", "ClassicConsole_01",
    "ClassicNightstand_01", "ArmChair_01", "Sofa_01", "dining_chair_02", "gothic_coffee_table",
    "fancy_picture_frame_01", "fancy_picture_frame_02", "brass_candleholders", "antique_ceramic_vase_01",
    "vintage_grandfather_clock_01", "ornate_mirror_01", "marble_bust_01", "mantel_clock_01", "Lantern_01"
)

$jobs = @()
foreach ($id in $Textures) {
    $f = Invoke-RestMethod "https://api.polyhaven.com/files/$id"
    foreach ($map in "Diffuse", "nor_dx", "Rough") {
        $e = $f.$map."2k".jpg
        if ($e) { $jobs += [pscustomobject]@{ Url = $e.url; Size = $e.size; Path = "Dokular\$id\$id`_$($map.ToLower())_2k.jpg" } }
    }
}
foreach ($id in $Models) {
    $files = Invoke-RestMethod "https://api.polyhaven.com/files/$id"
    # leaf / grass cut-outs live in separate *alpha maps that the glTF package does not include
    foreach ($p in $files.PSObject.Properties | Where-Object { $_.Name -like "*alpha" }) {
        $e = $p.Value."1k".jpg
        $part = if ($p.Name -eq "alpha") { "" } else { "_" + ($p.Name -replace "_alpha$", "") }
        $jobs += [pscustomobject]@{ Url = $e.url; Size = $e.size; Path = "Modeller\$id\textures\$id$part`_alpha_1k.jpg" }
    }
    $g = $files.gltf."1k".gltf
    $jobs += [pscustomobject]@{ Url = $g.url; Size = $g.size; Path = "Modeller\$id\$id.gltf" }
    foreach ($p in $g.include.PSObject.Properties) {
        $jobs += [pscustomobject]@{ Url = $p.Value.url; Size = $p.Value.size; Path = "Modeller\$id\$($p.Name -replace '/', '\')" }
    }
}
$total = ($jobs | Measure-Object Size -Sum).Sum
"{0} dosya, toplam {1:N0} MB ({2} doku seti, {3} model)" -f $jobs.Count, ($total / 1MB), $Textures.Count, $Models.Count
if ($SadeceBoyut) { return }

foreach ($j in $jobs) {
    $dst = Join-Path $root $j.Path
    if ((Test-Path $dst) -and (Get-Item $dst).Length -eq $j.Size) { continue }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Invoke-WebRequest -Uri $j.Url -OutFile $dst -UseBasicParsing
}
"indirildi -> $root"
