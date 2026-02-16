using System;
using UnityEngine;

public static class GameSignals
{
    public static Action OnWin;
    public static Action OnDefeat;
    public static Action<int> OnRunEssenceAwarded;

    // STICKY FLAGS
    public static bool WinRaisedThisRun { get; private set; }
    public static int WinRaiseFrame { get; private set; }

    public static void RaiseWin()
    {
        Debug.Log("[SIG] WIN raised");
        WinRaisedThisRun = true;
        WinRaiseFrame = Time.frameCount;

        if (OnWin == null) Debug.LogWarning("[SIG] WIN had 0 subscribers");
        OnWin?.Invoke();
    }

    public static void RaiseDefeat()
    {
        Debug.Log("[SIG] DEFEAT raised");
        OnDefeat?.Invoke();
    }

    public static void ResetStickyFlags()
    {
        WinRaisedThisRun = false;
        WinRaiseFrame = -1;
    }
}
