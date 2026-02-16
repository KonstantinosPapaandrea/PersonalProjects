using UnityEngine;

public static class RewardCalculator
{
    const int B = 20, W = 4, D = 10, SOFTCAP = 400, MIN_RUN_SEC = 180;

    public static int Calculate(MatchStats s, int todayEarned, bool firstWinToday)
    {
        float livesPct = Mathf.Clamp01((float)s.livesEnd / Mathf.Max(1, s.livesStart));
        float leakPct = s.enemiesSpawned == 0 ? 0f :
                         Mathf.Clamp01((float)s.enemiesLeaked / s.enemiesSpawned);

        float perf = 1.0f + 0.2f * livesPct - 0.2f * leakPct + (s.bossesKilled > 0 ? 0.2f : 0f);
        perf = Mathf.Clamp(perf, 0.6f, 1.4f);

        float streakMult = 1.0f + 0.05f * Mathf.Min(6, s.streakWins);

        int baseVal = B + W * s.wavesCleared + D * s.difficultyTier;
        float softcapMult = Mathf.Clamp01(1f - (float)todayEarned / SOFTCAP);

        float reward = baseVal * perf * streakMult * Mathf.Max(0.25f, softcapMult);

        if (!s.won) reward *= 0.25f; // consolation for losses
        if (s.runSeconds < MIN_RUN_SEC) reward *= 0.5f;

        int finalVal = Mathf.FloorToInt(reward);
        if (firstWinToday && s.won) finalVal += 50;

        return Mathf.Max(0, finalVal);
    }
}
