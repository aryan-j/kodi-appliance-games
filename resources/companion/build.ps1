param(
    [string]$Version = "0.3.0"
)

$companionDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = Join-Path $companionDirectory "KodiApplianceOverlay-$Version.exe"

if (Test-Path -LiteralPath $outputPath) {
    throw "Output already exists: $outputPath"
}

$sourcePaths = @(
    "ArcticOverlayUi.cs",
    "SystemControls.cs",
    "WebOverlayForm.cs",
    "KodiApplianceOverlay.cs"
) | ForEach-Object {
    Join-Path $companionDirectory $_
}
Add-Type `
    -Path $sourcePaths `
    -ReferencedAssemblies @(
        "System.dll",
        "System.Drawing.dll",
        "System.Web.Extensions.dll",
        "System.Windows.Forms.dll",
        (Join-Path $companionDirectory "Microsoft.Web.WebView2.Core.dll"),
        (Join-Path $companionDirectory "Microsoft.Web.WebView2.WinForms.dll")
    ) `
    -OutputAssembly $outputPath `
    -OutputType WindowsApplication

Get-Item -LiteralPath $outputPath
