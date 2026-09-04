param(
    [ValidateSet("Snapshot", "Connect")]
    [string]$Action = "Snapshot",
    [string]$Ssid
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

function Test-SafeSsid {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ($Value.Length -gt 64) { return $false }
    # Do not pass control characters, quotes, or line breaks to netsh.  This
    # is deliberately stricter than the Wi-Fi API's SSID rules because the
    # value is also passed as a quoted command argument.
    foreach ($character in $Value.ToCharArray()) {
        $code = [int][char]$character
        if ($code -lt 0x20 -or $code -eq 0x7F -or
            $code -eq 34 -or $code -eq 39) { return $false }
    }
    return $true
}

function Get-SafeSsid {
    param([string]$Value)
    if (-not (Test-SafeSsid $Value)) { return $null }
    return $Value.Trim()
}

function Get-WifiNetworks {
    $networks = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    $current = $null
    try {
        $lines = @(netsh.exe wlan show networks mode=bssid 2>$null)
        foreach ($line in $lines) {
            if ($line -match '^\s*SSID\s+\d+\s*:\s*(.*)\s*$') {
                if ($current -and $current.ssid -and -not $seen.ContainsKey($current.ssid)) {
                    $seen[$current.ssid] = $true
                    $null = $networks.Add($current)
                }
                $candidate = Get-SafeSsid $Matches[1]
                $current = if ($candidate) {
                    [ordered]@{
                        ssid = $candidate
                        signal = $null
                        authentication = $null
                    }
                } else { $null }
                continue
            }
            if (-not $current) { continue }
            if ($null -eq $current.authentication -and
                $line -match '^\s*Authentication\s*:\s*(.+?)\s*$') {
                $current.authentication = Clean-Text $Matches[1]
            }
            if ($null -eq $current.signal -and
                $line -match '^\s*Signal\s*:\s*(\d+)\s*%') {
                $current.signal = [int]$Matches[1]
            }
        }
        if ($current -and $current.ssid -and -not $seen.ContainsKey($current.ssid)) {
            $seen[$current.ssid] = $true
            $null = $networks.Add($current)
        }
    } catch { }

    $result = @()
    foreach ($network in $networks) { $result += $network }
    return $result
}

function Get-WifiProfileNames {
    $profiles = New-Object System.Collections.Generic.List[string]
    try {
        $lines = @(netsh.exe wlan show profiles 2>$null)
        foreach ($line in $lines) {
            if ($line -match '^\s*(?:All User Profile|User Profile)\s*:\s*(.+?)\s*$') {
                $profile = Get-SafeSsid $Matches[1]
                if ($profile -and -not $profiles.Contains($profile)) {
                    $null = $profiles.Add($profile)
                }
            }
        }
    } catch { }
    return $profiles
}

function Connect-Wifi {
    param([string]$RequestedSsid)
    $ssid = Get-SafeSsid $RequestedSsid
    if (-not $ssid) {
        return [ordered]@{
            result = "Invalid"
            ssid = $null
            message = "Invalid network name"
        }
    }

    $profile = Get-WifiProfileNames |
        Where-Object { $_ -ieq $ssid } |
        Select-Object -First 1
    if (-not $profile) {
        return [ordered]@{
            result = "NeedsSettings"
            ssid = $ssid
            message = "Network is not saved on this PC; open Network Settings to connect"
        }
    }

    try {
        # SSIDs containing quotes/control characters were rejected above.  No
        # credentials are read or emitted; Windows uses the saved profile.
        $null = netsh.exe wlan connect name="$profile" 2>$null
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            return [ordered]@{
                result = "Connected"
                ssid = $ssid
                message = "Connection requested"
            }
        }
    } catch { }
    return [ordered]@{
        result = "Failed"
        ssid = $ssid
        message = "Windows could not connect using the saved profile"
    }
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
        # Keep the JSON shape stable when only one access point is visible;
        # the WebView expects a collection even for a singleton result.
        networks = @(Get-WifiNetworks)
    }
}

function Get-BatteryLevel {
    param(
        [object]$DeviceInformation,
        [string]$InstanceId
    )
    # DeviceInformation may already contain this canonical Windows property.
    # Only return a value that is explicitly numeric and within the valid
    # range; a missing property is unknown, never zero.
    try {
        $properties = $DeviceInformation.Properties
        if ($properties) {
            foreach ($key in @("System.Devices.BatteryLifePercent", "System.Devices.BatteryLife")) {
                $value = $null
                if ($properties.ContainsKey($key)) { $value = $properties[$key] }
                if ($value -is [int] -or $value -is [long] -or $value -is [double] -or $value -is [decimal]) {
                    $number = [int]$value
                    if ($number -ge 0 -and $number -le 100) { return $number }
                }
                $raw = if ($null -ne $value) { [string]$value } else { "" }
                if ($raw -match "^\s*(\d{1,3})\s*%?\s*$") {
                    $number = [int]$Matches[1]
                    if ($number -ge 0 -and $number -le 100) { return $number }
                }
            }
        }
    } catch { }
    if ([string]::IsNullOrWhiteSpace($InstanceId)) { return $null }
    try {
        foreach ($key in @(
            "System.Devices.BatteryLifePercent",
            "DEVPKEY_Device_BatteryLevel"
        )) {
            $property = @(Get-PnpDeviceProperty -InstanceId $InstanceId `
                -KeyName $key -ErrorAction Stop |
                Select-Object -First 1)[0]
            $raw = if ($property) { [string]$property.Data } else { "" }
            if ($raw -match "^\s*(\d{1,3})\s*%?\s*$") {
                $value = [int]$Matches[1]
                if ($value -ge 0 -and $value -le 100) { return $value }
            }
        }
    } catch { }
    return $null
}

function Wait-WinRtOperation {
    param(
        $Operation,
        [Type]$ResultType,
        [int]$TimeoutMs = 2500
    )
    if ($null -eq $Operation -or $null -eq $ResultType) { return $null }
    try {
        $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
            Where-Object {
                $_.Name -eq "AsTask" -and
                $_.IsGenericMethodDefinition -and
                $_.GetGenericArguments().Count -eq 1 -and
                $_.GetParameters()[0].ParameterType.ToString() -match "IAsyncOperation"
            } |
            Select-Object -First 1
        if (-not $method) { return $null }
        $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        if (-not $task.Wait($TimeoutMs)) { return $null }
        return $task.Result
    } catch { return $null }
}

function Get-BluetoothDeviceRecords {
    param(
        [object]$DeviceInformationCollection,
        [object]$BluetoothDeviceType,
        [object]$BluetoothLeDeviceType,
        [bool]$LowEnergy
    )
    $devices = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    if ($null -eq $DeviceInformationCollection) { return @() }
    foreach ($info in $DeviceInformationCollection) {
        $name = Clean-Text $info.Name
        if (-not $name) { continue }
        # The device selectors return devices, but Windows can still expose
        # transport/service entries.  Keep only human-facing device names.
        if ($name -match "(?i)^(Generic |Microsoft )?Bluetooth (Radio|Device|Enumerator|LE Enumerator|RFCOMM Protocol|Protocol)" -or
            $name -match "(?i)(Generic (Access|Attribute) Profile|Generic Attribute Service|Device (Identification|Information) Service|Service Discovery Service|Avrcp Transport|Wireless Bluetooth\(R\))") { continue }

        $device = $null
        try {
            if ($LowEnergy) {
                $device = Wait-WinRtOperation -Operation ($BluetoothLeDeviceType::FromIdAsync($info.Id)) `
                    -ResultType $BluetoothLeDeviceType
            } else {
                $device = Wait-WinRtOperation -Operation ($BluetoothDeviceType::FromIdAsync($info.Id)) `
                    -ResultType $BluetoothDeviceType
            }
        } catch { }
        $status = "Unknown"
        if ($device) {
            try {
                $connectionStatus = $device.ConnectionStatus.ToString()
                if ($connectionStatus -eq "Connected") { $status = "Connected" }
                elseif ($connectionStatus -eq "Disconnected") { $status = "Disconnected" }
                else { $status = "Paired" }
            } catch { }
            try {
                $deviceName = Clean-Text $device.Name
                if ($deviceName) { $name = $deviceName }
            } catch { }
        }
        if (-not $seen.ContainsKey($name)) {
            $seen[$name] = $true
            $battery = Get-BatteryLevel -DeviceInformation $info -InstanceId ([string]$info.Id)
            $null = $devices.Add([ordered]@{
                name = $name
                status = $status
                battery = $battery
            })
        }
        if ($devices.Count -ge 20) { break }
    }
    return $devices
}

function Get-BluetoothSnapshot {
    $devices = New-Object System.Collections.Generic.List[object]
    $devicesByName = @{}
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop
        $deviceInformationType = [Windows.Devices.Enumeration.DeviceInformation, Windows, ContentType = WindowsRuntime]
        $deviceInformationCollectionType = [Windows.Devices.Enumeration.DeviceInformationCollection, Windows, ContentType = WindowsRuntime]
        $bluetoothDeviceType = [Windows.Devices.Bluetooth.BluetoothDevice, Windows, ContentType = WindowsRuntime]
        $bluetoothLeDeviceType = [Windows.Devices.Bluetooth.BluetoothLEDevice, Windows, ContentType = WindowsRuntime]

        $selectors = @(
            @{ value = $bluetoothDeviceType::GetDeviceSelector(); lowEnergy = $false },
            @{ value = $bluetoothLeDeviceType::GetDeviceSelector(); lowEnergy = $true }
        )
        foreach ($selector in $selectors) {
            if ([string]::IsNullOrWhiteSpace($selector.value)) { continue }
            # The one-argument overload is available on all supported Windows
            # builds.  Optional property-key overloads vary by projection and
            # can make enumeration fail before ConnectionStatus is read.
            $operation = $deviceInformationType::FindAllAsync($selector.value)
            $collection = Wait-WinRtOperation -Operation $operation `
                -ResultType $deviceInformationCollectionType -TimeoutMs 2500
            $records = Get-BluetoothDeviceRecords -DeviceInformationCollection $collection `
                -BluetoothDeviceType $bluetoothDeviceType `
                -BluetoothLeDeviceType $bluetoothLeDeviceType `
                -LowEnergy $selector.lowEnergy
            foreach ($record in $records) {
                $recordKey = ([string]$record.name).ToLowerInvariant()
                if ($devicesByName.ContainsKey($recordKey)) {
                    $existing = $devicesByName[$recordKey]
                    # Classic and LE selectors can describe the same device.
                    # Merge by name and let the authoritative Connected state
                    # win; never let a transport entry create a duplicate row.
                    if ([string]$record.status -eq "Connected") {
                        $existing.status = "Connected"
                    } elseif ([string]$existing.status -eq "Unknown" -and
                        [string]$record.status -ne "Unknown") {
                        $existing.status = $record.status
                    }
                    if ($null -eq $existing.battery -and $null -ne $record.battery) {
                        $existing.battery = $record.battery
                    }
                } else {
                    $devicesByName[$recordKey] = $record
                    $null = $devices.Add($record)
                }
                if ($devices.Count -ge 20) { break }
            }
            if ($devices.Count -ge 20) { break }
        }
    } catch { }

    $state = "Unknown"
    if ($devices.Count -gt 0) { $state = "Available" }
    $deviceArray = @()
    foreach ($item in $devices) { $deviceArray += $item }
    [ordered]@{
        state = $state
        devices = $deviceArray
    }
}

if ($Action -eq "Connect") {
    Connect-Wifi $Ssid | ConvertTo-Json -Compress -Depth 4
} else {
    [ordered]@{
        wifi = Get-WifiSnapshot
        bluetooth = Get-BluetoothSnapshot
    } | ConvertTo-Json -Compress -Depth 6
}
