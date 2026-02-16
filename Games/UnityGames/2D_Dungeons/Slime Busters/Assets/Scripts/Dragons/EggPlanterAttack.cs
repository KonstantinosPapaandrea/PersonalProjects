using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Tilemaps;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class EggPlanterAttack : AttackBehaviour
{
    [SerializeField] private bool autoFindPathByTag = true;
    [SerializeField] private string pathTilemapTag = "RoadTilemap";
    [SerializeField] private bool autoFindPathByName = true;
    [SerializeField] private string pathTilemapName = "Road";

    [Header("Prefabs & Layers")]
    [SerializeField] private Egg eggPrefab;
    [SerializeField] private EggThrow throwPrefab;           // standalone projectile prefab with ONLY EggThrow + visuals
    [SerializeField] private LayerMask enemyMask;

    [Header("Throw Settings")]
    [SerializeField] private float throwTravelTime = 0.45f;
    [SerializeField] private float throwArcHeight = 0.6f;
    [SerializeField] private float throwScatterRadius = 0.25f; // small in-cell jitter

    [Header("Path Landing (Tilemap)")]
    [SerializeField] private bool usePathTilemap = true;
    [SerializeField] private Tilemap pathTilemap;            // assign your road/path tilemap
    [SerializeField] private int pathSearchRadiusCells = 12;
    [SerializeField] private float inCellJitter = 0.28f;

    [Header("Auto-Seek (if no target)")]
    [SerializeField] private float autoSeekRadius = 8f;

    [Header("Base Stats")]
    [Min(1)][SerializeField] private int eggsPerCycle = 1;
    [Min(0.05f)][SerializeField] private float plantCooldown = 1.5f;
    [SerializeField] private float triggerRadius = 0.45f;
    [SerializeField] private float blastRadius = 1.0f;
    [SerializeField] private float eggDamage = 10f;
    [SerializeField] private float lifetime = 12f;
    [SerializeField] private int cap = 6;
    [SerializeField] private float fuse = 0f;

    [Header("Bonuses / Tech")]
    [SerializeField] private float bossBonus = 1f;
    [SerializeField] private int empoweredEveryN = 0;
    [SerializeField] private float empoweredDamageMult = 3f;
    [SerializeField] private float empoweredRadiusMult = 1.6f;
    [SerializeField] private bool empoweredIgnoreShields = false;

    [Header("Chain & Shrapnel")]
    [SerializeField] private float linkRadius = 0f;
    [SerializeField] private int shrapnelCount = 0;
    [SerializeField] private float shrapnelDamageMult = 0.25f;
    [SerializeField] private float shrapnelRange = 1.8f;

    [Header("Amplification (not CC)")]
    [Range(0f, 1f)][SerializeField] private float vulnPct = 0f;
    [SerializeField] private float vulnDur = 0f;

    [Header("Remote Detonate")]
    [SerializeField] private bool remoteDetonateEnabled = false;
    [SerializeField] private float remoteCooldown = 8f;

    // runtime
    private float remoteCooldownTimer = 0f;
    private float cooldownTimer = 0f;
    private readonly List<Egg> activeEggs = new();
    private int eggSpawnCounter = 0;
    private int pendingThrows = 0; // eggs currently flying (not landed yet)

    public override bool RequiresTarget => false;
    public override bool CanFireNow() => cooldownTimer <= 0f;
    public void SetPathTilemap(Tilemap map) { pathTilemap = map; }

    public override void Bind(Dragon d)
    {
        base.Bind(d);
        if (enemyMask == 0 && owner != null) enemyMask = owner.enemyMask;
        if (enemyMask == 0) enemyMask = ~0;

        // NEW: path tilemap auto-wire
        if (usePathTilemap && !pathTilemap)
        {
            // 1) Global provider
            if (RoadMapProvider.Instance) pathTilemap = RoadMapProvider.Instance.tilemap;

            // 2) Tag
            if (!pathTilemap && autoFindPathByTag)
            {
                var go = GameObject.FindWithTag(pathTilemapTag);
                if (go) pathTilemap = SLB_ComponentCache.Get<Tilemap>(go);
            }

            // 3) Name
            if (!pathTilemap && autoFindPathByName)
            {
                var go = GameObject.Find(pathTilemapName);
                if (go) pathTilemap = SLB_ComponentCache.Get<Tilemap>(go);
            }
        }
    }


    void Update()
    {
        if (cooldownTimer > 0f) cooldownTimer -= Time.deltaTime;
        if (remoteCooldownTimer > 0f) remoteCooldownTimer -= Time.deltaTime;
        CleanupList();
    }

    public override void Fire(Vector3 origin, Enemy target, Dragon owner)
    {
        if (cooldownTimer > 0f) return;

        // robust mask fallback
        if (enemyMask == 0 && owner != null) enemyMask = owner.enemyMask;
        if (enemyMask == 0) enemyMask = ~0;

        // (optional) guard for missing prefabs
        if (!eggPrefab)
        {
            SLB_Debug.LogError("[EggPlanterAttack] Egg prefab not assigned.", this);
            cooldownTimer = plantCooldown;
            return;
        }
  

        if (!target) target = FindNearestEnemy(origin, autoSeekRadius);

        int available = cap - (activeEggs.Count + pendingThrows);
        int toSpawn = Mathf.Clamp(available, 0, eggsPerCycle);
        if (toSpawn <= 0)
        {
            cooldownTimer = plantCooldown;
            return;
        }

        Vector3 anchor = origin;

        for (int i = 0; i < toSpawn; i++)
        {
            bool empowered = empoweredEveryN > 0 && ((eggSpawnCounter + 1) % empoweredEveryN == 0);
            var prms = BuildParams(empowered);

            // 1) Prefer landing on the path tilemap
            if (usePathTilemap && pathTilemap && TryGetPathLanding(anchor, out Vector3 endOnPath))
            {
                LaunchThrow(origin, endOnPath, prms);
                eggSpawnCounter++;
                continue;
            }

          

            // Fallback: drop slightly ahead of the dragon
            Vector3 forward = (target ? (target.transform.position - origin) : Vector3.right).normalized;
            Vector3 dropPos = origin + forward * 1.1f;
            SpawnEggAt(dropPos, prms);
        }

        cooldownTimer = plantCooldown;
    }

    private void LaunchThrow(Vector3 start, Vector3 end, Egg.Params prms)
    {
        if (!throwPrefab || ThrowPrefabLooksWrong())
        {
            // misassigned prefab—just drop at the intended end point
            SpawnEggAt(end, prms);
            return;
        }

        var thrower = Instantiate(throwPrefab, start, Quaternion.identity);
        pendingThrows++;
        thrower.LaunchWithParams(
            start: start,
            end: end,
            eggPrefab: eggPrefab,
            p: prms,
            host: this,
            travelTimeOverride: throwTravelTime,
            arcHeightOverride: throwArcHeight
        );
    }

    // Called by EggThrow when landing to keep cap accurate
    public void RegisterEgg(Egg e)
    {
        pendingThrows = Mathf.Max(0, pendingThrows - 1);
        if (!e) return;
        e.OnDespawn += HandleEggDespawn;
        activeEggs.Add(e);
    }

    public bool TryRemoteDetonate()
    {
        if (!remoteDetonateEnabled || remoteCooldownTimer > 0f) return false;
        for (int i = 0; i < activeEggs.Count; i++)
        {
            if (activeEggs[i] != null) activeEggs[i].TriggerDetonation();
        }
        remoteCooldownTimer = remoteCooldown;
        return true;
    }

    public void TryPlant() // optional: route same logic for any external callers
    {
        Fire(transform.position, FindNearestEnemy(transform.position, autoSeekRadius), owner);
    }

    private void HandleEggDespawn(Egg e)
    {
        activeEggs.Remove(e);
    }

    private void CleanupList()
    {
        for (int i = activeEggs.Count - 1; i >= 0; i--)
            if (activeEggs[i] == null) activeEggs.RemoveAt(i);
    }

    private bool ThrowPrefabLooksWrong()
    {
        if (!throwPrefab) return true;
        var go = throwPrefab.gameObject;
        return go.GetComponentInChildren<Dragon>(true) != null
            || go.GetComponentInChildren<EggPlanterAttack>(true) != null;
    }

    // ===== Helpers =====

    private Enemy FindNearestEnemy(Vector3 from, float radius)
    {
        var hits = new Collider2D[32];
        int n = Physics2D.OverlapCircleNonAlloc(from, radius, hits, enemyMask);
        Enemy best = null;
        float bestD2 = float.PositiveInfinity;
        for (int i = 0; i < n; i++)
        {
            var e = hits[i] ? hits[i].GetComponentInParent<Enemy>() : null;
            if (!e) continue;
            float d2 = (e.transform.position - from).sqrMagnitude;
            if (d2 < bestD2) { bestD2 = d2; best = e; }
        }
        return best;
    }

    private bool TryGetPathLanding(Vector3 anchor, out Vector3 world)
    {
        world = anchor;
        if (!pathTilemap) return false;

        Vector3Int startCell = pathTilemap.WorldToCell(anchor);
        if (pathTilemap.HasTile(startCell))
        {
            world = JitteredCellCenter(startCell);
            return true;
        }

        for (int r = 1; r <= Mathf.Max(1, pathSearchRadiusCells); r++)
        {
            for (int dy = -r; dy <= r; dy++)
            {
                for (int dx = -r; dx <= r; dx++)
                {
                    if (Mathf.Max(Mathf.Abs(dx), Mathf.Abs(dy)) != r) continue;
                    var c = new Vector3Int(startCell.x + dx, startCell.y + dy, startCell.z);
                    if (pathTilemap.HasTile(c))
                    {
                        world = JitteredCellCenter(c);
                        return true;
                    }
                }
            }
        }
        return false;
    }

    private Vector3 JitteredCellCenter(Vector3Int cell)
    {
        Vector3 center = pathTilemap.GetCellCenterWorld(cell);
        Vector2 jitter = Random.insideUnitCircle * Mathf.Max(0f, inCellJitter);
        center.x += jitter.x;
        center.y += jitter.y;
        center.z = 0f;
        return center;
    }

    private Egg.Params BuildParams(bool empowered)
    {
        return new Egg.Params
        {
            damage = eggDamage * (empowered ? empoweredDamageMult : 1f),
            blastRadius = blastRadius * (empowered ? empoweredRadiusMult : 1f),
            triggerRadius = triggerRadius,
            fuse = fuse,
            lifetime = lifetime,

            bossBonus = bossBonus,
            ignoreShields = empowered && empoweredIgnoreShields,

            linkRadius = linkRadius,
            shrapnelCount = shrapnelCount,
            shrapnelDamageMult = shrapnelDamageMult,
            shrapnelRange = shrapnelRange,

            vulnPct = vulnPct,
            vulnDur = vulnDur,

            enemyMask = enemyMask
        };
    }

    private void SpawnEggAt(Vector3 pos, Egg.Params prms)
    {
        var e = Instantiate(eggPrefab, pos, Quaternion.identity);
        eggSpawnCounter++;
        RegisterEgg(e);
        e.Init(prms);
    }

    // ==== Upgrade hooks ====
    public void AddEggsPerCycle(int delta) => eggsPerCycle = Mathf.Max(1, eggsPerCycle + delta);
    public void MulEggDamage(float m) => eggDamage *= Mathf.Max(0f, m);
    public void MulPlantCooldown(float m) => plantCooldown = Mathf.Max(0.05f, plantCooldown * m);
    public void AddEggCap(int delta) => cap = Mathf.Max(1, cap + delta);
    public void MulBlastRadius(float m) => blastRadius = Mathf.Max(0.05f, blastRadius * m);
    public void MulEggLifetime(float m) => lifetime = Mathf.Max(0.1f, lifetime * m);
    public void SetTriggerFuse(float seconds) => fuse = Mathf.Max(0f, seconds);
    public void SetBossBonus(float mult) => bossBonus = Mathf.Max(0f, mult);
    public void EnableEmpoweredEveryN(int n, float dmgMult, float radiusMult, bool ignoreShields)
    { empoweredEveryN = Mathf.Max(0, n); empoweredDamageMult = dmgMult; empoweredRadiusMult = radiusMult; empoweredIgnoreShields = ignoreShields; }
    public void EnableTrapLink(float radius) => linkRadius = Mathf.Max(0f, radius);
    public void EnableShrapnel(int count, float dmgMult, float range)
    { shrapnelCount = Mathf.Max(0, count); shrapnelDamageMult = Mathf.Max(0f, dmgMult); shrapnelRange = Mathf.Max(0f, range); }
    public void EnableRemoteDetonate(float cooldown)
    { remoteDetonateEnabled = true; remoteCooldown = Mathf.Max(0.1f, cooldown); }
    public void EnableVulnerability(float pct, float dur)
    { vulnPct = Mathf.Clamp01(pct); vulnDur = Mathf.Max(0f, dur); }
}

}
