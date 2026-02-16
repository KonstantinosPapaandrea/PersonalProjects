using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Builds the wave list for **one level** using your Long-Form rules:
/// - Wave 1-2: Green-only runway
/// - Build (~20%): Green -> Green+Blue
/// - Feature (~40%): gradually add previously unlocked types (DarkBlue->Purple->Pink),
///                   late feature can lightly touch White/Black/Fast
/// - Pressure (rest): add Fast/White/Black, and (late) Yellow/Tank
/// - Boss: last wave only; boss enters mid-timeline (wave still opens with Greens)
/// This class does *no* spawning, *no* scaling, and *no* UI.
/// </summary>
public static class WaveComposer
{
    public enum Phase { WarmUp, Build, Feature, Pressure }

    public class Inputs
    {
        // Level context
        public int level;               // 1..∞
        public int totalWaves;          // Long-Form: 11 + level
        public string regionId = "default";

        // Slime roster (assign from LevelManager)
        public SlimeDef Green, Blue, DarkBlue, Purple, Pink, White, Black, Yellow, Fast, Tank;
        public SlimeDef HealingBoss, HPBoss, ResistanceBoss;
        public SlimeDef RegionFallbackBoss; // optional from RegionSO

        // Pacing knobs
        public int warmupGreenCount = 12;    // per lane on Wave 1
        public int baseLaneCount = 2;
        public int maxLaneCount = 5;
        public float baseInterval = 0.7f;    // gentle baseline
        public float minSpawnInterval = 0.04f;

        // Phase proportions
        public int warmupWaves = 2;          // always 2
        public float buildFrac = 0.20f;      // ~20% of total waves
        public float featureFrac = 0.40f;    // ~40% of total waves
    }

    /// <summary>Compose all waves for the given level.</summary>
    public static List<Wave> Compose(Inputs I)
    {
        var waves = new List<Wave>(I.totalWaves);

        // Phase split
        int buildCount = Mathf.Max(3, Mathf.RoundToInt(I.totalWaves * I.buildFrac));
        int featureCount = Mathf.Max(4, Mathf.RoundToInt(I.totalWaves * I.featureFrac));
        int warmEnd = I.warmupWaves;
        int buildEnd = warmEnd + buildCount;
        int featEnd = buildEnd + featureCount;

        // helpers
        bool IsUnlocked(SlimeDef s)
        {
            if (!s) return false;
            if (s == I.Green) return true;                 // L1
            if (s == I.Blue) return I.level >= 2;
            if (s == I.DarkBlue) return I.level >= 3;
            if (s == I.Purple) return I.level >= 4;
            if (s == I.Pink) return I.level >= 5;
            if (s == I.White) return I.level >= 6;
            if (s == I.Black) return I.level >= 7;
            if (s == I.Yellow) return I.level >= 8;
            if (s == I.Tank) return I.level >= 9;
            if (s == I.Fast) return I.level >= 3;         // allowed mid/late in-level
            return false;
        }

        SlimeDef BossForLevel(int level)
        {
            if (level < 11) return null;
            // Locked blocks for 11-25, then rotate every 5
            if (level >= 11 && level <= 15) return I.HealingBoss ?? I.RegionFallbackBoss;
            if (level >= 16 && level <= 20) return I.HPBoss ?? I.RegionFallbackBoss;
            if (level >= 21 && level <= 25) return I.ResistanceBoss ?? I.RegionFallbackBoss;

            int block = (level - 11) / 5; // 0-based
            int which = block % 3;
            return which switch
            {
                0 => I.HealingBoss ?? I.RegionFallbackBoss,
                1 => I.HPBoss ?? I.RegionFallbackBoss,
                _ => I.ResistanceBoss ?? I.RegionFallbackBoss
            };
        }

        int LaneCountFor(int waveIndex1)
        {
            float t = (float)(waveIndex1 - 1) / Mathf.Max(1, I.totalWaves - 1);
            int lanes = I.baseLaneCount;
            if (t >= 0.25f) lanes++;
            if (t >= 0.65f) lanes++;
            return Mathf.Clamp(lanes, I.baseLaneCount, I.maxLaneCount);
        }

        Phase PhaseFor(int waveIndex1)
        {
            if (waveIndex1 <= warmEnd) return Phase.WarmUp;
            if (waveIndex1 <= buildEnd) return Phase.Build;
            if (waveIndex1 <= featEnd) return Phase.Feature;
            return Phase.Pressure;
        }

        // Build each wave
        for (int i = 1; i <= I.totalWaves; i++)
        {
            var w = new Wave { name = $"L{I.level}-W{i}", useTimeline = true, groups = new List<WaveGroup>() };
            int lanes = LaneCountFor(i);

            // Faster pacing *later* in the level (never spiky)
            float tLevel = (float)(i - 1) / Mathf.Max(1, I.totalWaves - 1);
            float baseInterval = Mathf.Lerp(I.baseInterval, Mathf.Max(0.25f, I.baseInterval * 0.8f), tLevel);

            // helper to add a lane stream
            void AddGroupSafe(SlimeDef s, int count, float interval, float start)
            {
                if (!s || count <= 0) return;
                w.groups.Add(new WaveGroup
                {
                    slime = s,
                    count = count,
                    interval = Mathf.Max(I.minSpawnInterval, interval),
                    startTime = start
                });
            }

            // Always open with GREENS (runway)
            int runwayGreensPerLane = (i == 1) ? I.warmupGreenCount : Mathf.RoundToInt(I.warmupGreenCount * 1.2f);
            float runwayInterval = Mathf.Max(0.45f, I.baseInterval);
            for (int lane = 0; lane < lanes; lane++)
                AddGroupSafe(I.Green, runwayGreensPerLane, runwayInterval * (1f + lane * 0.08f), lane * 0.6f);

            // Common growth baseline
            int commonCount = Mathf.RoundToInt(8 + i * 0.75f);

            // Phase-specific adds
            Phase phase = PhaseFor(i);
            bool lateFeature = (phase == Phase.Feature) && (i >= warmEnd + buildCount + Mathf.Max(2, featureCount / 2));

            switch (phase)
            {
                case Phase.WarmUp:
                    // greens only
                    break;

                case Phase.Build:
                    if (IsUnlocked(I.Blue))
                        for (int lane = 0; lane < lanes; lane++)
                            AddGroupSafe(I.Blue, Mathf.RoundToInt(commonCount * 0.6f), baseInterval * (0.95f + lane * 0.08f), 2.0f + lane * 0.8f);
                    break;

                case Phase.Feature:
                    {
                        var teaching = new List<SlimeDef>();
                        if (IsUnlocked(I.DarkBlue)) teaching.Add(I.DarkBlue);
                        if (IsUnlocked(I.Purple)) teaching.Add(I.Purple);
                        if (IsUnlocked(I.Pink)) teaching.Add(I.Pink);

                        for (int lane = 0; lane < Mathf.Min(lanes, 2); lane++)
                        {
                            var pick = teaching.Count > 0 ? teaching[(lane + i) % teaching.Count] : I.Blue;
                            AddGroupSafe(pick, Mathf.RoundToInt(commonCount * 0.9f), baseInterval * (0.9f + lane * 0.1f), 2.0f + lane * 0.8f);
                        }

                        if (lateFeature)
                        {
                            if (IsUnlocked(I.White)) AddGroupSafe(I.White, Mathf.RoundToInt(commonCount * 0.6f), baseInterval * 1.0f, 3.0f);
                            if (IsUnlocked(I.Black)) AddGroupSafe(I.Black, Mathf.RoundToInt(commonCount * 0.5f), baseInterval * 0.95f, 3.8f);
                            if (IsUnlocked(I.Fast)) AddGroupSafe(I.Fast, Mathf.RoundToInt(commonCount * 0.4f), baseInterval * 0.55f, 2.6f);
                        }
                        break;
                    }

                case Phase.Pressure:
                    if (IsUnlocked(I.Fast)) AddGroupSafe(I.Fast, Mathf.RoundToInt(commonCount * 0.7f), baseInterval * 0.55f, 2.2f);
                    if (IsUnlocked(I.Blue)) AddGroupSafe(I.Blue, Mathf.RoundToInt(commonCount * 0.9f), baseInterval * 0.85f, 2.8f);
                    if (IsUnlocked(I.DarkBlue)) AddGroupSafe(I.DarkBlue, Mathf.RoundToInt(commonCount * 0.85f), baseInterval * 0.90f, 3.1f);
                    if (IsUnlocked(I.Purple)) AddGroupSafe(I.Purple, Mathf.RoundToInt(commonCount * 0.8f), baseInterval * 0.90f, 3.8f);
                    if (IsUnlocked(I.Pink)) AddGroupSafe(I.Pink, Mathf.RoundToInt(commonCount * 0.7f), baseInterval * 0.95f, 4.6f);
                    if (IsUnlocked(I.White)) AddGroupSafe(I.White, Mathf.RoundToInt(commonCount * 0.7f), baseInterval * 1.00f, 5.4f);
                    if (IsUnlocked(I.Black)) AddGroupSafe(I.Black, Mathf.RoundToInt(commonCount * 0.6f), baseInterval * 0.95f, 6.2f);
                    if (IsUnlocked(I.Yellow)) AddGroupSafe(I.Yellow, Mathf.Max(1, Mathf.RoundToInt(commonCount * 0.35f)), baseInterval * 1.10f, 7.0f);
                    if (IsUnlocked(I.Tank)) AddGroupSafe(I.Tank, Mathf.Max(1, Mathf.RoundToInt(commonCount * 0.2f)), baseInterval * 1.20f, 7.8f);
                    break;
            }

            // Final wave boss (boss block only) — add mid-timeline
            bool isFinal = (i == I.totalWaves);
            if (isFinal)
            {
                var boss = BossForLevel(I.level);
                if (boss != null)
                {
                    AddGroupSafe(boss, 1, 1.6f, 6.0f);
                    if (IsUnlocked(I.Tank)) AddGroupSafe(I.Tank, 1 + I.level / 12, 1.0f, 7.5f);
                    if (IsUnlocked(I.White)) AddGroupSafe(I.White, Mathf.Clamp(2 + I.level / 10, 2, 6), 0.95f, 8.0f);
                    if (IsUnlocked(I.Fast)) AddGroupSafe(I.Fast, Mathf.Clamp(6 + I.level / 4, 6, 16), 0.55f, 9.0f);
                }
            }

            waves.Add(w);
        }

        return waves;
    }
}
