using SlimeBusters.Internal;
namespace SlimeBusters
{
﻿using UnityEngine;

[DefaultExecutionOrder(-1000)] // run Awake very early
public class EssenceRunReporter : MonoBehaviour
{
    public static EssenceRunReporter I { get; private set; }

    EnemySpawner spawner;
    int startLives;
    bool started;
    bool awarded;

    public int StartBalance { get; private set; }
    public int RunAward { get; private set; }

    void Awake()
    {
        I = this;
        spawner = SLB_Locator.Get<EnemySpawner>();

        // Subscribe EARLY (Awake), not OnEnable
        GameSignals.OnWin += OnWin;
        GameSignals.OnDefeat += OnDefeat;
        SLB_Debug.Log("[Reporter] Subscribed to WIN/DEFEAT (Awake)");

        if (spawner)
        {
            spawner.onWaveStarted += OnWaveStarted;
            SLB_Debug.Log("[Reporter] Subscribed to onWaveStarted");
        }

        // If WIN already happened before we existed, handle it now
        if (GameSignals.WinRaisedThisRun && !awarded)
        {
            SLB_Debug.Log("[Reporter] WIN was already raised. Replaying award.");
            // Wait one frame so DragonEssenceManager/others finish their own work
            StartCoroutine(CoAwardNextFrame());
        }
    }

    System.Collections.IEnumerator CoAwardNextFrame() { yield return null; TryAward(true); }

    void OnDestroy()
    {
        GameSignals.OnWin -= OnWin;
        GameSignals.OnDefeat -= OnDefeat;
        if (spawner) spawner.onWaveStarted -= OnWaveStarted;
    }

    void OnWaveStarted(int level, int wave1Based)
    {
        if (started) return;
        started = true;
        startLives = Mathf.Max(1, GameManager.Instance ? GameManager.Instance.lives : 1);
        var mgr = DragonEssenceManager.Instance;
        StartBalance = mgr ? mgr.Balance : 0;
        SLB_Debug.Log($"[Reporter] First wave started. LivesStart={startLives}, StartBalance={StartBalance}");
    }

    void OnWin() { SLB_Debug.Log("[Reporter] OnWin received"); TryAward(true); }
    void OnDefeat() { SLB_Debug.Log("[Reporter] OnDefeat received"); TryAward(false); }

    public void TryAward(bool won)
    {
        SLB_Debug.Log("[Reporter] TryAward entered");
        if (awarded) { SLB_Debug.Log("[Reporter] Already awarded. Skip."); return; }
        awarded = true;
        SLB_Debug.Log("got here");

        var mgr = DragonEssenceManager.Instance;
        if (!mgr) { SLB_Debug.LogWarning("[Reporter] Essence manager missing."); return; }
        SLB_Debug.Log("got here");

        int currentLives = GameManager.Instance ? GameManager.Instance.lives : (won ? 1 : 0);
        int wavesCleared = spawner ? spawner.WavesCleared : 0;

        var stats = new MatchStats
        {
            wavesCleared = wavesCleared,
            won = won,
            livesStart = started ? startLives : Mathf.Max(1, currentLives),
            livesEnd = Mathf.Max(0, currentLives),
            enemiesSpawned = EnemyCounter.I ? EnemyCounter.I.Spawned : 0,
            enemiesLeaked = EnemyCounter.I ? EnemyCounter.I.Leaked : 0,
            bossesKilled = 0,
            runSeconds = Time.timeSinceLevelLoad,
            difficultyTier = 0,
            streakWins = mgr.StreakWins
        };
        SLB_Debug.Log("got here");
        int before = mgr.Balance;
        int reward = mgr.Award(stats);         // ← use returned reward (not inferred)
        RunAward = reward;                     // ← authoritative for this run
        SLB_Debug.Log("got here");

        GameSignals.OnRunEssenceAwarded?.Invoke(RunAward);
        SLB_Debug.Log($"[Reporter] Awarded. Won={won}, Reward={reward}, Balance {before}→{mgr.Balance}");

    }
}

}
