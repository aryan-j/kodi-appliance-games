param(
    [ValidateSet("WiFi", "Bluetooth")]
    [string]$Kind,
    [ValidateSet("Status", "Toggle")]
    [string]$Action = "Status"
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$radioType = [Windows.Devices.Radios.Radio, Windows, ContentType = WindowsRuntime]
$radioKindType = [Windows.Devices.Radios.RadioKind, Windows, ContentType = WindowsRuntime]
$radioStateType = [Windows.Devices.Radios.RadioState, Windows, ContentType = WindowsRuntime]

function Wait-WinRtOperation {
    param(
        $Operation,
        [Type]$ResultType
    )
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            $_.IsGenericMethodDefinition -and
            $_.GetGenericArguments().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

$radioListType = [System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]
$radios = Wait-WinRtOperation -Operation ($radioType::GetRadiosAsync()) -ResultType $radioListType
$targetKind = if ($Kind -eq "WiFi") { $radioKindType::WiFi } else { $radioKindType::Bluetooth }
$radio = $radios | Where-Object { $_.Kind -eq $targetKind } | Select-Object -First 1

if (-not $radio) {
    Write-Output "Unavailable"
    exit 1
}

if ($Action -eq "Toggle") {
    $accessType = [Windows.Devices.Radios.RadioAccessStatus, Windows, ContentType = WindowsRuntime]
    $access = Wait-WinRtOperation -Operation ($radioType::RequestAccessAsync()) -ResultType $accessType
    if ($access.ToString() -ne "Allowed") {
        Write-Output "Denied"
        exit 2
    }
    $desired = if ($radio.State -eq $radioStateType::On) {
        $radioStateType::Off
    } else {
        $radioStateType::On
    }
    $null = Wait-WinRtOperation -Operation ($radio.SetStateAsync($desired)) -ResultType $accessType
}

Write-Output $radio.State.ToString()
