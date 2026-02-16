using System.Collections.Generic;
using UnityEngine;
using TMPro;

/// <summary>
/// Owns the *level* lifecycle:
/// - decides how many waves (Long-Form: 11 + level)
/// - composes waves via WaveComposer
/// - initializes EnemySpawner
/// - handles win UI & saving next level
/// </summary>
public class LevelManager : MonoBehaviour
{
    [Header("References")]
    public EnemySpawner spawner;
    public RegionSO region;              // optional, only to read regionId / boss fallback
    public TMP_Text waveText;            // label for "Level X - Wave Y/N"
    public GameObject winPanel;
    public TMP_Text winText;

    [Header("Long-Form length (locked)")]
    public int longFormBase = 11;        // totalWaves = longFormBase + level

    [Header("Phase proportions")]
    [Range(0.1f, 0.35f)] public float buildFrac = 0.20f;
    [Range(0.30f, 0.50f)] public float featureFrac = 0.40f;

    [Header("Pacing knobs")]
    public int warmupGreenCount = 12;
    public int baseLaneCount = 2;
    public int maxLaneCount = 5;
    public float baseInterval = 0.7f;
    public float minSpawnInterval = 0.04f;

    [Header("Scaling by LEVEL (x=level)")]
    public AnimationCurve hpMultByLevel = AnimationCurve.Linear(1, 1, 50, 12);
    public AnimationCurve speedMultByLevel = AnimationCurve.Linear(1, 1, 50, 1.35f);
    public AnimationCurve bountyMultByLevel = AnimationCurve.Linear(1, 1, 50, 4f);
    public AnimationCurve resistByLevel; // optional
    public bool tinyWaveShaping = false; // ±5% inside level

    [Header("Roster (assign SlimeDefs)")]
    public SlimeDef Green, Blue, DarkBlue, Purple, Pink, White, Black, Yellow, Fast, Tank;

    [Header("Bosses (final wave only on boss levels)")]
    public SlimeDef HealingBoss, HPBoss, ResistanceBoss;

    // runtime
    int currentLevel = 1;
    bool levelClearedThisSession = false;

    void Awake()
    {
        //ResetProgressForRegion();
        if (!spawner) spawner = FindObjectOfType<EnemySpawner>();

        if (winPanel) winPanel.SetActive(false);
        if (winText) winText.text = "";

        // Load level per region
        string regionId = (region && !string.IsNullOrEmpty(region.regionId)) ? region.regionId : "default";
        currentLevel = RegionProgress.LoadLevel(regionId, 1);

        BuildAndBindLevel(currentLevel);
        HookSpawnerEvents(regionId);
    }

    void BuildAndBindLevel(int level)
    {
        int totalWaves = longFormBase + Mathf.Max(1, level); // L1=12, L10=21, etc.

        // Compose waves
        var inputs = new WaveComposer.Inputs
        {
            level = level,
            totalWaves = totalWaves,
            regionId = (region && !string.IsNullOrEmpty(region.regionId)) ? region.regionId : "default",

            // roster
            Green = Green,
            Blue = Blue,
            DarkBlue = DarkBlue,
            Purple = Purple,
            Pink = Pink,
            White = White,
            Black = Black,
            Yellow = Yellow,
            Fast = Fast,
            Tank = Tank,
            HealingBoss = HealingBoss,
            HPBoss = HPBoss,
            ResistanceBoss = ResistanceBoss,
            RegionFallbackBoss = region ? region.boss : null,

            // pacing
            warmupGreenCount = warmupGreenCount,
            baseLaneCount = baseLaneCount,
            maxLaneCount = maxLaneCount,
            baseInterval = baseInterval,
            minSpawnInterval = minSpawnInterval,

            // phases
            warmupWaves = 2,
            buildFrac = buildFrac,
            featureFrac = featureFrac
        };

        List<Wave> waves = WaveComposer.Compose(inputs);

        // Hand waves to spawner with scaling
        spawner.Initialize(
            level, waves,
            hpMultByLevel, speedMultByLevel, bountyMultByLevel, resistByLevel,
            tinyWaveShaping, waveText
        );
    }

    void HookSpawnerEvents(string regionId)
    {
        spawner.onAllWavesCleared += (level) =>
        {
            if (levelClearedThisSession) return;
            levelClearedThisSession = true;

            // Save next level
            RegionProgress.SaveLevel(regionId, level + 1);

            // Show win UI
            if (winPanel) winPanel.SetActive(true);
            if (winText) winText.text = $"YOU WIN!\nLevel {level} Cleared";

            GameSignals.RaiseWin();
        };
    }

    // UI hooks
    public void StartWaveButton()
    {
        if (levelClearedThisSession) return;
        if (spawner == null) return;

        if (!spawner.IsWaveRunning && waveText != null && string.IsNullOrEmpty(waveText.text))
            spawner.StartFirstWave();
        else
            spawner.StartNextWave();
    }

    // (Optional) Reset progress button
    public void ResetProgressForRegion()
    {   
        string regionId = (region && !string.IsNullOrEmpty(region.regionId)) ? region.regionId : "default";
        PlayerPrefs.DeleteKey($"endlesslevel.progress.{regionId}");
    }
}
