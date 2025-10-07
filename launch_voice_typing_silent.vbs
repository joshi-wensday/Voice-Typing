' Voice Typing Silent Launcher (No Console Window)
' Double-click this file to launch Voice Typing without showing a console window

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory of this script
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Check if virtual environment exists
venvPython = scriptDir & "\venv\Scripts\python.exe"
If Not fso.FileExists(venvPython) Then
    MsgBox "Error: Virtual environment not found!" & vbCrLf & vbCrLf & _
           "Please run: python scripts\setup_dev.py", vbCritical, "Voice Typing"
    WScript.Quit 1
End If

' Launch Voice Typing (window hidden, no console)
' 0 = hidden, False = don't wait
WshShell.Run """" & venvPython & """ -m voice_typing", 0, False

