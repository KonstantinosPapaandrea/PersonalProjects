using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;
using TMPro;
using SlimeBusters;

/// <summary>
/// Runs a prebuilt wave list (timelines & spawn timing only).
/// It does not decide *what* to spawn—that’s WaveComposer’s job.
/// It applies per-level scaling when instantiating enemies.
/// </summary>
public class EnemySpawner : MonoBehaviour
{
    public static EnemySpawner I { get; private set; }   // back-compat for older scripts
    public int WavesCleared { get; private set; }        // back-compat counter

    [Header("Path")]
    public Transform pathParent;
    Transform[] path;

    [Header("Enemy Prefab")]
    public GameObject enemyPrefab;

    [Header("UI (optional)")]
    public TMP_Text waveText;

    [Header("Spawn Safety")]
    public float minSpawnInterval = 0.04f; // clamp to avoid same-frame spam

    // Per-level scaling curves (x=level); set by LevelManager
    [HideInInspector] public AnimationCurve hpMultByLevel;
    [HideInInspector] public AnimationCurve speedMultByLevel;
    [HideInInspector] public AnimationCurve bountyMultByLevel;
    [HideInInspector] public AnimationCurve resistByLevel; // optional
    [HideInInspector] public bool harderByWaveInsideLevel = false;

    // Runtime
    List<Wave> waves;
    int currentLevel = 1;
    int currentWaveIndex = -1;
    Coroutine runCo;

    public bool IsWaveRunning => runCo != null;
    public event Action<int, int> onWaveStarted; // (level, waveIndex1)
    public event Action<int, int> onWaveCleared; // (level, waveIndex1)
    public event Action<int> onAllWavesCleared; // (level)

    void Awake()
    {
        I = this;   // keep legacy access working (Enemy.cs uses EnemySpawner.I)

        // cache path
        if (pathParent != null)
        {
            int n = pathParent.childCount;
            path = new Transform[n];
            for (int i = 0; i < n; i++) path[i] = pathParent.GetChild(i);
        }
    }

    /// <summary>Initialize spawner with waves for a specific level and configure scaling.</summary>
    public void Initialize(int level, List<Wave> waveList,
        AnimationCurve hpLvl, AnimationCurve spdLvl, AnimationCurve bntyLvl, AnimationCurve resistLvl,
        bool waveShaping, TMP_Text waveLabel = null)
    {
        currentLevel = Mathf.Max(1, level);
        waves = waveList ?? new List<Wave>();
        currentWaveIndex = -1;
        hpMultByLevel = hpLvl;
        speedMultByLevel = spdLvl;
        bountyMultByLevel = bntyLvl;
        resistByLevel = resistLvl;
        harderByWaveInsideLevel = waveShaping;
        if (waveLabel) waveText = waveLabel;
    }

    public void StartFirstWave()
    {
        if (IsWaveRunning || waves == null || waves.Count == 0) return;
        currentWaveIndex = -1;
        StartNextWave();
    }

    public void StartNextWave()
    {
        if (IsWaveRunning || waves == null || waves.Count == 0) return;
        currentWaveIndex = Mathf.Clamp(currentWaveIndex + 1, 0, waves.Count - 1);
        runCo = StartCoroutine(RunWaveRoutine(currentWaveIndex));
    }

    IEnumerator RunWaveRoutine(int waveIndex)
    {
        int wave1 = waveIndex + 1;
        waveText?.SetText($"Level {currentLevel} - Wave {wave1}/{waves.Count}");
        onWaveStarted?.Invoke(currentLevel, wave1);

        var wave = waves[waveIndex];

        // Run groups; if timeline, parallel by startTime
        if (wave.useTimeline)
        {
            int running = 0;
            foreach (var g in wave.groups)
            {
                running++;
                StartCoroutine(SpawnGroup(g, () => running--));
            }
            yield return new WaitUntil(() => running == 0);
        }
        else
        {
            foreach (var g in wave.groups)
            {
                float step = (g.interval <= 0f) ? minSpawnInterval : g.interval;
                for (int i = 0; i < g.count; i++)
                {
                    SpawnOne(g.slime, wave1);
                    if (i < g.count - 1) yield return new WaitForSeconds(step);
                }
            }
        }

        // Wait until field is clear
        while (FindObjectsOfType<Enemy>().Length > 0) yield return null;

      onWaveCleared?.Invoke(currentLevel, wave1);
WavesCleared++;                         // <— increment here
GameManager.Instance?.AddCoins(100);

        runCo = null;

        bool last = (currentWaveIndex >= waves.Count - 1);
        if (last) onAllWavesCleared?.Invoke(currentLevel);
    }

    IEnumerator SpawnGroup(WaveGroup g, System.Action onDone)
    {
        if (g == null || g.slime == null) { onDone?.Invoke(); yield break; }
        if (g.startTime > 0f) yield return new WaitForSeconds(g.startTime);

        float step = (g.interval <= 0f) ? minSpawnInterval : g.interval;
        for (int i = 0; i < g.count; i++)
        {
            SpawnOne(g.slime, currentWaveIndex + 1);
            if (i < g.count - 1) yield return new WaitForSeconds(step);
        }
        onDone?.Invoke();
    }

    void SpawnOne(SlimeDef def, int wave1Based)
    {
        if (!enemyPrefab) { Debug.LogError("[Spawner] enemyPrefab missing"); return; }
        var go = Instantiate(enemyPrefab);
        var e = go.GetComponent<Enemy>();
        if (!e) { Debug.LogError("[Spawner] Prefab missing Enemy"); Destroy(go); return; }

        e.Init(path, def);

        // ----- Per-level scaling (no heavy wave-scaling) -----
        float hpM = (hpMultByLevel != null) ? Mathf.Max(0.5f, hpMultByLevel.Evaluate(currentLevel)) : 1f;
        float spdM = (speedMultByLevel != null) ? Mathf.Max(0.5f, speedMultByLevel.Evaluate(currentLevel)) : 1f;
        float bntM = (bountyMultByLevel != null) ? Mathf.Max(0.5f, bountyMultByLevel.Evaluate(currentLevel)) : 1f;


        // Optional tiny shaping within a level (±5%)
        float waveFactor = 1f;
        if (harderByWaveInsideLevel && waves.Count > 1)
        {
            float t = (wave1Based - 1f) / (waves.Count - 1f);
            waveFactor = Mathf.Lerp(0.95f, 1.05f, t);
        }
        var resist = new SlimeDef.Resistances();

        if (resistByLevel != null)
        {
            int v = Mathf.Clamp(Mathf.RoundToInt(resistByLevel.Evaluate(currentLevel)), 0, 100);
            resist.fire = resist.ice = resist.lightning = resist.egg = resist.crystal = v;
        }
        e.ApplyWaveScaling(hpM * waveFactor, spdM * waveFactor, bntM * waveFactor, resist);
    }
}
