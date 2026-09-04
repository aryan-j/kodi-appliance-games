param(
    [ValidateSet("Snapshot")]
    [string]$Action = "Snapshot"
)

# Read-only connectivity snapshot for the WebView2 pause overlay.
#
# This script deliberately does not expose network credentials, connection
# profiles beyond the visible SSID, or any device identifiers.  It is invoked
# only on a connectivity panel open/refresh and is bounded by the host process.
$ErrorActionPreference = "SilentlyContinue"

function Clean-Text {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    $text = [string]$Value
    $text = [regex]::Replace($text, "[\x00-\x1F\x7F]", "")
    $text = $text.Trim()
    if ($text.Length -gt 120) { return $text.Substring(0, 120) }
    return $text
}

function Get-WifiSnapshot {
    $adapter = $null
    try {
        $adapter = @(Get-NetAdapter -ErrorAction Stop |
            Where-Object {
                $_.Name -match "(?i)wi-?fi|wireless|802\.11" -or
                $_.InterfaceDescription -match "(?i)wi-?fi|wireless|802\.11"
            } |
            Sort-Object @{ Expression = { if ($_.Status -eq "Up") { 0 } else { 1 } } }, Name |
            Select-Object -First 1)[0]
    } catch { }

    $ssid = $null
    $signal = $null
    $netshState = $null
    try {
        $wlanLines = @(netsh.exe wlan show interfaces 2>$null)
        foreach ($line in $wlanLines) {
            if (-not $ssid -and $line -match "^\s*SSID\s*:\s*(.+?)\s*$") {
                $ssid = Clean-Text $Matches[1]
            }
            if ($line -match "^\s*State\s*:\s*(.+?)\s*$") {
                $netshState = Clean-Text $Matches[1]
            }
            if ($null -eq $signal -and $line -match "^\s*Signal\s*:\s*(\d+)\s*%") {
                $signal = [int]$Matches[1]
            }
        }
    } catch { }

    $profile = $null
    try {
        if ($adapter) {
            $profile = @(Get-NetConnectionProfile -InterfaceAlias $adapter.Name |
                Select-Object -First 1)[0]
        }
    } catch { }

    $isUp = $adapter -and ([string]$adapter.Status -eq "Up")
    $isConnected = $isUp -and (
        $netshState -match "(?i)^connected$" -or $profile -or $ssid)
    $state = "Unknown"
    if ($isConnected) { $state = "Connected" }
    elseif ($isUp) { $state = "Available" }
    elseif ($adapter) { $state = "Off" }

    $displaySsid = $ssid
    if (-not $displaySsid -and $profile) { $displaySsid = Clean-Text $profile.Name }
    $displayAdapter = $null
    if ($adapter) { $displayAdapter = Clean-Text $adapter.Name }
    $displayLinkSpeed = $null
    if ($adapter) { $displayLinkSpeed = Clean-Text $adapter.LinkSpeed }

    [ordered]@{
        state = $state
        ssid = $displaySsid
        adapter = $displayAdapter
        signal = $signal
        linkSpeed = $displayLinkSpeed
    }
}

function Get-BatteryLevel {
    param([string]$InstanceId)
    if ([string]::IsNullOrWhiteSpace($InstanceId)) { return $null }
    try {
        $property = @(Get-PnpDeviceProperty -InstanceId $InstanceId `
            -KeyName "DEVPKEY_Device_BatteryLevel" -ErrorAction Stop |
            Select-Object -First 1)[0]
        $raw = if ($property) { [string]$property.Data } else { "" }
        if ($raw -match "^\s*(\d{1,3})\s*%?\s*$") {
            $value = [int]$Matches[1]
            if ($value -ge 0 -and $value -le 100) { return $value }
        }
    } catch { }
    return $null
}

function Get-BluetoothSnapshot {
    $all = @()
    try { $all = @(Get-PnpDevice -Class Bluetooth -ErrorAction Stop) } catch { }

    $devices = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    foreach ($device in $all) {
        $name = Clean-Text $device.FriendlyName
        if (-not $name) { $name = Clean-Text $device.Name }
        # Hide Windows' transport/adapter entries while retaining user devices
        # such as "Bluetooth Keyboard" and "Bluetooth Headphones".
        if (-not $name -or
            $name -match "(?i)^(Generic |Microsoft )?Bluetooth (Radio|Device|Enumerator|LE Enumerator|RFCOMM Protocol|Protocol)" -or
            $name -match "(?i)(Generic (Access|Attribute) Profile|Generic Attribute Service|Device (Identification|Information) Service|Service Discovery Service|Avrcp Transport|Wireless Bluetooth\(R\))") { continue }
        if ($seen.ContainsKey($name)) { continue }
        $seen[$name] = $true
        $instanceId = [string]$device.InstanceId
        # Get-PnpDevice already exposes Present; avoid a second full PnP scan.
        $isPresent = [bool]$device.Present
        $status = "Paired"
        if ($isPresent -and [string]$device.Status -eq "OK") { $status = "Connected" }
        $battery = $null
        # Battery properties are only meaningful while the device is present;
        # limit the slower property query to connected devices.
        if ($status -eq "Connected") { $battery = Get-BatteryLevel $instanceId }
        $devices.Add([ordered]@{
            name = $name
            status = $status
            battery = $battery
        })
        if ($devices.Count -ge 20) { break }
    }

    $state = "Unknown"
    if ($devices.Count -gt 0) { $state = "Available" }
    $deviceArray = @()
    foreach ($item in $devices) { $deviceArray += $item }
    [ordered]@{
        state = $state
        devices = $deviceArray
    }
}

if ($Action -eq "Snapshot") {
    [ordered]@{
        wifi = Get-WifiSnapshot
        bluetooth = Get-BluetoothSnapshot
    } | ConvertTo-Json -Compress -Depth 6
}
