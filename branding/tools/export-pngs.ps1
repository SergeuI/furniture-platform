param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName WindowsBase

function New-Brush($hex) {
    return [System.Windows.Media.SolidColorBrush](
        [System.Windows.Media.ColorConverter]::ConvertFromString($hex)
    )
}

function Draw-Path($context, $data, $fill, $scale, $offsetX, $offsetY) {
    $geometry = ([System.Windows.Media.Geometry]::Parse($data)).Clone()
    $geometry.Transform = New-Object System.Windows.Media.MatrixTransform($scale, 0, 0, $scale, $offsetX, $offsetY)
    $context.DrawGeometry((New-Brush $fill), $null, $geometry)
}

function Draw-MpSymbol($context, $scale, $offsetX, $offsetY, $metal = "#66717b", $green = "#39d353") {
    Draw-Path $context "M0 248V0h86l96 138L278 0h82v248h-78V112l-86 126h-28L78 112v136z" $metal $scale $offsetX $offsetY
    Draw-Path $context "M420 248V0h154c80 0 132 49 132 124s-52 124-132 124h-76v0zm78-70h70c36 0 58-20 58-54s-22-54-58-54h-70z" $metal $scale $offsetX $offsetY
    Draw-Path $context "M0 302l76-43v68L0 368z" $green $scale $offsetX $offsetY
}

function Draw-Text($context, $text, $x, $y, $size, $weight, $color) {
    $typeface = New-Object System.Windows.Media.Typeface(
        (New-Object System.Windows.Media.FontFamily("Segoe UI")),
        [System.Windows.FontStyles]::Normal,
        $weight,
        [System.Windows.FontStretches]::Normal
    )
    $formatted = New-Object System.Windows.Media.FormattedText(
        $text,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Windows.FlowDirection]::LeftToRight,
        $typeface,
        $size,
        (New-Brush $color),
        1.0
    )
    $context.DrawText($formatted, (New-Object System.Windows.Point($x, $y)))
}

function Save-Png($relativePath, $width, $height, [scriptblock]$draw) {
    $visual = New-Object System.Windows.Media.DrawingVisual
    $context = $visual.RenderOpen()
    & $draw $context
    $context.Close()

    $bitmap = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
        $width,
        $height,
        96,
        96,
        [System.Windows.Media.PixelFormats]::Pbgra32
    )
    $bitmap.Render($visual)

    $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))

    $path = Join-Path $Root $relativePath
    $stream = [System.IO.File]::Create($path)
    try {
        $encoder.Save($stream)
    }
    finally {
        $stream.Dispose()
    }
}

function Save-LogoPng($path, $darkBackground, $lightText) {
    Save-Png $path 1440 480 {
        param($context)
        if ($darkBackground) {
            $context.DrawRectangle((New-Brush "#0d141a"), $null, (New-Object System.Windows.Rect(0, 0, 1440, 480)))
        }
        elseif ($path -notlike "*transparent*") {
            $context.DrawRectangle((New-Brush "#f7fafc"), $null, (New-Object System.Windows.Rect(0, 0, 1440, 480)))
        }
        Draw-MpSymbol $context 0.56 92 92 "#66717b" "#39d353"
        $mainColor = if ($lightText) { "#f7fafc" } else { "#111820" }
        $mutedColor = if ($lightText) { "#a8b1ba" } else { "#46515c" }
        Draw-Text $context "MProject" 665 144 78 ([System.Windows.FontWeights]::Bold) $mainColor
        Draw-Text $context ".furniture" 1018 144 78 ([System.Windows.FontWeights]::Bold) "#39d353"
        Draw-Text $context "FURNITURE PRODUCTION PLATFORM" 670 252 24 ([System.Windows.FontWeights]::Medium) $mutedColor
    }
}

Save-LogoPng "branding\logo\mproject-logo-transparent.png" $false $true
Save-LogoPng "branding\logo\mproject-logo-dark.png" $true $true
Save-LogoPng "branding\logo\mproject-logo-light.png" $false $false
Save-LogoPng "branding\logo\mproject-logo-flat.png" $true $true

Save-Png "branding\logo\mp-symbol-3d.png" 512 512 {
    param($context)
    Draw-MpSymbol $context 0.58 26 102 "#66717b" "#39d353"
}

Save-Png "branding\logo\mp-symbol-flat.png" 512 512 {
    param($context)
    Draw-MpSymbol $context 0.58 26 104 "#202932" "#39d353"
}

foreach ($size in 16, 32, 48, 64) {
    Save-Png "branding\icons\favicon-$size.png" $size $size {
        param($context)
        $context.DrawRoundedRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, $size, $size)), ($size * 0.22), ($size * 0.22))
        Draw-MpSymbol $context ($size / 900) ($size * 0.12) ($size * 0.28) "#66717b" "#39d353"
    }
}

foreach ($size in 192, 512) {
    Save-Png "branding\icons\app-icon-$size.png" $size $size {
        param($context)
        $context.DrawRoundedRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, $size, $size)), ($size * 0.2), ($size * 0.2))
        Draw-MpSymbol $context ($size / 900) ($size * 0.12) ($size * 0.28) "#66717b" "#39d353"
    }
}

Save-Png "branding\icons\app-icon-maskable-512.png" 512 512 {
    param($context)
    $context.DrawRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, 512, 512)))
    Draw-MpSymbol $context (512 / 900) (512 * 0.12) (512 * 0.28) "#66717b" "#39d353"
}

Save-Png "branding\social\telegram-avatar-512.png" 512 512 {
    param($context)
    $context.DrawEllipse((New-Brush "#111820"), $null, (New-Object System.Windows.Point(256, 256)), 256, 256)
    Draw-MpSymbol $context (512 / 900) (512 * 0.12) (512 * 0.28) "#66717b" "#39d353"
}

Save-Png "branding\social\social-preview.png" 1200 630 {
    param($context)
    $context.DrawRectangle((New-Brush "#0d141a"), $null, (New-Object System.Windows.Rect(0, 0, 1200, 630)))
    Draw-MpSymbol $context 0.48 86 150 "#66717b" "#39d353"
    Draw-Text $context "MProject" 585 230 72 ([System.Windows.FontWeights]::Bold) "#f7fafc"
    Draw-Text $context ".furniture" 905 230 72 ([System.Windows.FontWeights]::Bold) "#39d353"
    Draw-Text $context "FURNITURE PRODUCTION PLATFORM" 590 318 24 ([System.Windows.FontWeights]::Medium) "#a8b1ba"
}

Write-Output "Brand PNG assets generated."
