' pyADR silent launcher — run pyADR.bat with no visible cmd window.
' Use pyADR.bat directly (or pyADR_debug.bat) if you need to see startup output.
' Path-relative: resolves pyADR.bat from this script's own directory.
Dim fso, scriptDir, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = scriptDir & "\pyADR.bat"
CreateObject("Wscript.Shell").Run """" & batPath & """", 0, False
