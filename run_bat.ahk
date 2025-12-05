#NoEnv
#SingleInstance Force
SendMode, Event
SetKeyDelay, 0, 50

; -------------------------
; GLOBAL FLAG FOR SOFT-LOCK
; -------------------------
InputLocked := false

; -------------------------
; Focus Fallout 3
; -------------------------
SetTitleMatchMode, 2
IfWinExist, Fallout3
{
    WinActivate
    WinWaitActive, Fallout3
    Sleep, 300
}
else
{
    ExitApp
}

; -------------------------
; BEGIN INPUT LOCK + FAILSAFE
; -------------------------
InputLocked := true
BlockInput, On
; If something goes wrong, force-unlock & exit after 8 seconds
SetTimer, ForceUnblock, 8000

; -------------------------
; EXECUTE: open console, run "bat etw", close console
; -------------------------
Sleep, 300
Send, ``
Sleep, 150

Send, bat mng
Sleep, 150
Send, {Enter}
Sleep, 1000

Send, ``
Sleep, 300

; -------------------------
; NORMAL CLEANUP
; -------------------------
SetTimer, ForceUnblock, Off
BlockInput, Off
InputLocked := false
ExitApp

; -------------------------
; FAILSAFE LABEL:
; Ensures input is restored even if something hangs
; -------------------------
ForceUnblock:
BlockInput, Off
InputLocked := false
SetTimer, ForceUnblock, Off
ExitApp
return


; -------------------------
; SOFT LOCK HOTKEYS:
; Eat common movement/interaction keys while InputLocked = true
; -------------------------
#If (InputLocked)

*w::return
*a::return
*s::return
*d::return

*Space::return
*LButton::return
*RButton::return

*e::return
*q::return
*f::return
*r::return
*Tab::return
*Shift::return
*Ctrl::return

#If
