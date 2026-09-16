' Autogenererad dold startare for DrJonsson-Drain
Option Explicit
Dim sh, q, rc
Set sh = CreateObject("WScript.Shell")
q = Chr(34)
sh.CurrentDirectory = "E:\CHAT-RTX\CLAUDECODE GENERAL BRAIN\APP ideas\aaron-prints"
rc = sh.Run("cmd.exe /c " & q & "E:\CHAT-RTX\CLAUDECODE GENERAL BRAIN\APP ideas\aaron-prints\schedule\run_drain.cmd" & q, 0, True)
WScript.Quit rc
