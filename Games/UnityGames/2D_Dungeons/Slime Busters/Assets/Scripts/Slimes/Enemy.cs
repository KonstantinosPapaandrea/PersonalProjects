using UnityEngine;
using System.Collections;
using System.Collections.Generic;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class Enemy : MonoBehaviour
{// --- NEW: runtime scaling knobs (set by spawner per wave) ---
    float hpScale = 1f;
    float speedScale = 1f;
    float bountyScale = 1f;
    SlimeDef.Resistances runtimeResBonus;  // percent points 0..100 per type
    [SerializeField] AudioClip deathSFX;
    [SerializeField] Vector2 deathPitchRange = new Vector2(0.96f, 1.04f);
    [SerializeField, Range(0f, 10f)] float deathVol = 0.9f;  // add on this GO
    [Header("Path")]
    [SerializeField] Transform[] waypoints;
    int wpIndex = 0;

    [Header("Runtime")]
    [SerializeField] SlimeDef def;
    [SerializeField] float hp, shield;
    float baseMoveSpeed;
    float speedMultiplier = 1f;              // for Slow
    Coroutine slowRoutine, regenRoutine;
    [Header("Debug (read-only)")]
    [SerializeField] float effectiveMaxHpDebug;
    [SerializeField] float hpPercentDebug;
    [Header("Debug (Inspector)")]
    [SerializeField, Tooltip("From SlimeDef (design-time).")]
    SlimeDef.Resistances baseResDebug;

    [SerializeField, Tooltip("After stacking all active resistance auras. 0..100 each.")]
    SlimeDef.Resistances effectiveResDebug;

    [Header("Visual")]
    [SerializeField] SpriteRenderer sr;

    // ---- STUN ----
    bool stunned = false;
    Coroutine stunRoutine;

    // ---- ARMOR SHRED (stacking) ----
    // Each stack increases damage taken by shredPctPerStack (e.g., 0.15 = +15% per stack)
    int shredStacks = 0;
    float shredPctPerStack = 0f;
    // We track one coroutine per stack so overlapping applications can expire independently
    readonly List<Coroutine> shredCoroutines = new List<Coroutine>();
    [SerializeField] int shredMaxStacks = 10;   // safety cap

    // --- INIT from spawner ---
    public void Init(Transform[] path, SlimeDef slimeDef)
    {
        def = slimeDef;
        waypoints = path;

        transform.localScale = Vector3.one * (def ? def.scale : 1f);
        hp = def.maxHP;
        shield = def.shielded ? def.shieldHP : 0;
        baseMoveSpeed = def.moveSpeed;
        speedMultiplier = 1f;

        if (sr == null) sr = GetComponentInChildren<SpriteRenderer>();
        if (sr && def.overrideSprite) sr.sprite = def.overrideSprite;
        if (sr) sr.color = def.tint;

        wpIndex = 0;
        if (waypoints != null && waypoints.Length > 0)
        {
            transform.position = waypoints[0].position;
            if (waypoints.Length > 1) wpIndex = 1;
        }

        if (def.regenerates && regenRoutine == null)
            regenRoutine = StartCoroutine(RegenCo());

        // ← NOW clamp with a valid def + any active auras
        hp = Mathf.Min(hp, EffectiveMaxHP);

        // ← AND NOW attach/bind the emitter (def is set and valid)
        EnsureAuraEmitter();
    }

    void Awake()
    {
        if (sr == null) sr = GetComponentInChildren<SpriteRenderer>();
    }

    void Update()
    {
        MoveAlongPath();

        // debug mirrors
        effectiveMaxHpDebug = EffectiveMaxHP;
        hpPercentDebug = (effectiveMaxHpDebug > 0f) ? hp / effectiveMaxHpDebug : 0f;
        if (def != null)
        {
            baseResDebug = def.resistances;
            effectiveResDebug.physical = GetResistancePercent(DamageType.Physical);
            effectiveResDebug.fire = GetResistancePercent(DamageType.Fire);
            effectiveResDebug.ice = GetResistancePercent(DamageType.Ice);
            effectiveResDebug.lightning = GetResistancePercent(DamageType.Lightning);
            effectiveResDebug.egg = GetResistancePercent(DamageType.Egg);
            effectiveResDebug.crystal = GetResistancePercent(DamageType.Crystal);
        }
    }
    // ---- AURA RUNTIME (Max HP stacking) ----
    readonly Dictionary<int, float> maxHpAuraContrib = new Dictionary<int, float>();
    float TotalMaxHpAuraBonus => SumMaxHpAura(); // sum of all percent bonuses (e.g., 0.15 + 0.10 = 0.25)
    float EffectiveMaxHP => def != null ? def.maxHP * hpScale * (1f + Mathf.Max(0f, TotalMaxHpAuraBonus)) : 1f;
    public void ReceiveHeal(float amount)
    {
        if (amount <= 0f) return;
        hp = Mathf.Min(hp + amount, EffectiveMaxHP);
    }
    public void RegisterMaxHpAura(int sourceId, float bonusPercent)
    {
        // bonusPercent is like 0.20 for +20%
        if (bonusPercent <= 0f) return;
        maxHpAuraContrib[sourceId] = bonusPercent;

        // If effective cap increased, don't modify current HP unless above new cap
        if (hp > EffectiveMaxHP) hp = EffectiveMaxHP;
    }

    public void UnregisterMaxHpAura(int sourceId)
    {
        if (maxHpAuraContrib.Remove(sourceId))
        {
            // If cap shrinks, clamp current HP down to new cap
            if (hp > EffectiveMaxHP) hp = EffectiveMaxHP;
        }
    }
    // ---- AURA RUNTIME (Resistances stacking) ----
    readonly Dictionary<int, SlimeDef.Resistances> resistAuraContrib = new Dictionary<int, SlimeDef.Resistances>();

    public void RegisterResistanceAura(int sourceId, SlimeDef.Resistances bonus)
    {
        // accept zero-safe; caller filters usually
        resistAuraContrib[sourceId] = bonus;
    }

    public void UnregisterResistanceAura(int sourceId)
    {
        resistAuraContrib.Remove(sourceId);
    }

    // Sum resistance percent points coming from auras (0..100)
    int SumResistanceAura(DamageType type)
    {
        int sum = 0;
        foreach (var kv in resistAuraContrib)
        {
            var b = kv.Value;
            switch (type)
            {
                case DamageType.Physical: sum += b.physical; break;
                case DamageType.Fire: sum += b.fire; break;
                case DamageType.Ice: sum += b.ice; break;
                case DamageType.Lightning: sum += b.lightning; break;
                case DamageType.Egg: sum += b.egg; break;
                case DamageType.Crystal: sum += b.crystal; break;
            }
        }
        return Mathf.Clamp(sum, 0, 100);
    }
    int GetResistancePercent(DamageType type)
    {
        if (def == null) return 0;

        var r = def.resistances;
        int basePct = 0;
        switch (type)
        {
            case DamageType.Physical: basePct = Mathf.Clamp(r.physical, 0, 100); break;
            case DamageType.Fire: basePct = Mathf.Clamp(r.fire, 0, 100); break;
            case DamageType.Ice: basePct = Mathf.Clamp(r.ice, 0, 100); break;
            case DamageType.Lightning: basePct = Mathf.Clamp(r.lightning, 0, 100); break;
            case DamageType.Egg: basePct = Mathf.Clamp(r.egg, 0, 100); break;
            case DamageType.Crystal: basePct = Mathf.Clamp(r.crystal, 0, 100); break;
            default: return 0;
        }

        int auraPct = SumResistanceAura(type);

        // NEW: runtime per-wave bonus
        int runPct = 0;
        switch (type)
        {
            case DamageType.Physical: runPct = runtimeResBonus.physical; break;
            case DamageType.Fire: runPct = runtimeResBonus.fire; break;
            case DamageType.Ice: runPct = runtimeResBonus.ice; break;
            case DamageType.Lightning: runPct = runtimeResBonus.lightning; break;
            case DamageType.Egg: runPct = runtimeResBonus.egg; break;
            case DamageType.Crystal: runPct = runtimeResBonus.crystal; break;
        }

        return Mathf.Clamp(basePct + auraPct + runPct, 0, 100);
    }

    void EnsureAuraEmitter()
    {
        var existing = SLB_ComponentCache.Get<AuraEmitter>(this);

        bool hasHeal = def != null && def.healingAuraPerSecond > 0f;
        bool hasMaxHP = def != null && def.maxHpAuraPercent > 0f;

        bool hasResist =
            def != null && (
                def.resistanceAuraBonus.physical > 0 ||
                def.resistanceAuraBonus.fire > 0 ||
                def.resistanceAuraBonus.ice > 0 ||
                def.resistanceAuraBonus.lightning > 0 ||
                def.resistanceAuraBonus.egg > 0 ||
                def.resistanceAuraBonus.crystal > 0
            );

        bool needsAura = def != null && def.auraRadius > 0f && (hasHeal || hasMaxHP || hasResist);

        if (needsAura)
        {
            if (!existing) existing = gameObject.AddComponent<AuraEmitter>();
            existing.Bind(this, def);
        }
        else
        {
            if (existing) Destroy(existing);
        }
    }

    float SumMaxHpAura()
    {
        float s = 0f;
        foreach (var kv in maxHpAuraContrib) s += kv.Value;
        return s;
    }

    void MoveAlongPath()
    {
        if (waypoints == null || waypoints.Length == 0) return;
        if (stunned) return; // pause movement while stunned

        if (wpIndex >= waypoints.Length) { ReachGoal(); return; }

        Vector3 target = waypoints[wpIndex].position;
        float step = baseMoveSpeed * speedMultiplier * speedScale * Time.deltaTime; // NEW: * speedScale
        transform.position = Vector3.MoveTowards(transform.position, target, step);

        if ((transform.position - target).sqrMagnitude < 0.0025f) wpIndex++;
    }

    // --- Damage & effects ---
    // IMPORTANT: signature stays EXACTLY the same (callers rely on it)
    public void TakeDamage(float dmg, DamageType type = DamageType.Generic)
    {
        if (dmg <= 0f) return;

        // --- compute effective damage in float (no rounding anywhere) ---
        float fdmg = dmg;

        // Resistances (percent 0..100)
        int resistPct = GetResistancePercent(type);

        // Legacy lightning bool: if designer used old flag and no % set, treat as 100% (your old behavior)
        if (type == DamageType.Lightning && def != null && def.lightningResist && resistPct == 0)
            resistPct = 100;

        float resistMult = Mathf.Clamp01(1f - resistPct / 100f);
        fdmg *= resistMult;                     // AFTER resist → may be fractional (e.g., 0.5)

        // Armor shred AFTER resist (stacks add linearly)
        float shredMult = 1f + Mathf.Max(0, shredStacks) * Mathf.Max(0f, shredPctPerStack);
        fdmg *= shredMult;

        if (fdmg <= 0f) return;

        // Shields absorb first (fractional is fine)
        if (def != null && def.shielded && shield > 0f)
        {
            float use = Mathf.Min(shield, fdmg);
            shield -= use;
            fdmg -= use;
            if (fdmg <= 0f) return;
        }

        // HP subtract in float; small hits accumulate naturally
        hp -= fdmg;
        if (hp <= 0f) Die();
    }

    // Pull resistance % from SlimeDef.Resistances (0..100). Safe if not present.
    

    public void ApplySlow(float pct, float duration)
    {
        if (def != null && def.slowImmune) return;
        if (slowRoutine != null) StopCoroutine(slowRoutine);
        slowRoutine = StartCoroutine(SlowCo(pct, duration));
    }

    IEnumerator SlowCo(float pct, float duration)
    {
        speedMultiplier = Mathf.Clamp01(1f - pct);
        yield return new WaitForSeconds(duration);
        speedMultiplier = 1f;
        slowRoutine = null;
    }

    IEnumerator RegenCo()
    {
        var wait = new WaitForSeconds(1f);
        while (true)
        {
            hp = Mathf.Min(hp + def.regenPerSecond, def.maxHP);
            yield return wait;
        }
    }

    // Spawn/init this enemy at a specific position, continuing from a waypoint index
    public void InitAt(Transform[] path, SlimeDef slimeDef, int nextWaypointIndex, Vector3 startPos)
    {
        def = slimeDef;
        waypoints = path;
        wpIndex = Mathf.Clamp(nextWaypointIndex, 0, (waypoints != null ? waypoints.Length - 1 : 0));
        transform.position = startPos;

        hp = def.maxHP;
        shield = def.shielded ? def.shieldHP : 0;
        baseMoveSpeed = def.moveSpeed;
        speedMultiplier = 1f;

        var rb = SLB_ComponentCache.Get<Rigidbody2D>(this); if (rb) rb.simulated = true;
        var cols = GetComponentsInChildren<Collider2D>(true); foreach (var c in cols) c.enabled = true;

        if (sr == null) sr = GetComponentInChildren<SpriteRenderer>();
        if (sr && def.overrideSprite) sr.sprite = def.overrideSprite;
        if (sr) sr.color = def.tint;

        if (regenRoutine != null) { StopCoroutine(regenRoutine); regenRoutine = null; }
        if (def.regenerates) regenRoutine = StartCoroutine(RegenCo());

        if (waypoints != null && wpIndex < waypoints.Length)
        {
            if ((transform.position - waypoints[wpIndex].position).sqrMagnitude < 0.0004f && wpIndex + 1 < waypoints.Length)
                wpIndex++;
        }
        hp = Mathf.Min(hp, EffectiveMaxHP);
        EnsureAuraEmitter();

    }
    // NEW: called by spawner right after Init(...)
    public void ApplyWaveScaling(float hpMult, float speedMult, float bountyMult, SlimeDef.Resistances resistBonus)
    {
        hpScale = Mathf.Max(0.01f, hpMult);
        speedScale = Mathf.Max(0.01f, speedMult);
        bountyScale = Mathf.Max(0.01f, bountyMult);
        runtimeResBonus = resistBonus;

        // If HP cap grew/shrank, clamp current HP to new cap
        hp = Mathf.Min(hp, EffectiveMaxHP);
    }


    void Die()
    {
    
        GameManager.Instance.AddCoins(def != null ? Mathf.RoundToInt(def.bounty * bountyScale) : 1); // NEW

        if (def != null && def.splitsOnDeath && def.splitChilds != null && def.splitCount > 0)
        {
            Vector3 spawnPos = transform.position;
            int nextIndex = Mathf.Clamp(wpIndex, 0, waypoints?.Length - 1 ?? 0);

            Vector3 forward = Vector3.zero;
            if (waypoints != null && nextIndex < waypoints.Length)
                forward = (waypoints[nextIndex].position - spawnPos).normalized;
            if (forward.sqrMagnitude < 1e-6f) forward = Vector3.right;

            for (int j = 0; j < def.splitChilds.Length; j++)
            {
                for (int i = 0; i < def.splitCount; i++)
                {
                    var prefab = EnemySpawner.I ? EnemySpawner.I.enemyPrefab : null;
                    var go = Instantiate(prefab ? prefab : gameObject, transform.parent);
                    var child = SLB_ComponentCache.Get<Enemy>(go);

                    var rb = SLB_ComponentCache.Get<Rigidbody2D>(go); if (rb) rb.simulated = true;
                    foreach (var c in go.GetComponentsInChildren<Collider2D>(true)) c.enabled = true;

                    Vector2 lateral = Random.insideUnitCircle * 0.06f;
                    Vector3 start = spawnPos + forward * 0.10f + (Vector3)lateral;
                    child.InitAt(waypoints, def.splitChilds[j], nextIndex, start);
                }
            }
        }
        if (SoundPlayer.I) SoundPlayer.I.PlayAtJitter(deathSFX, transform.position, deathVol, deathPitchRange, 1f, 25f);

        Destroy(gameObject);
    }

    Transform[] GetRemainingPath()
    {
        if (waypoints == null || wpIndex >= waypoints.Length) return waypoints;
        int n = waypoints.Length - (wpIndex - 0);
        Transform[] rest = new Transform[n];
        for (int i = 0; i < n; i++) rest[i] = waypoints[wpIndex - 0 + i];
        if (rest.Length > 0) rest[0] = CreateTempWaypointAt(transform.position, rest[0].parent);
        return rest;
    }

    Transform CreateTempWaypointAt(Vector3 pos, Transform parent)
    {
        GameObject w = new GameObject("TempWP");
        w.transform.SetPositionAndRotation(pos, Quaternion.identity);
        if (parent) w.transform.SetParent(parent);
        Destroy(w, 2f);
        return w.transform;
    }

    void ReachGoal()
    {
        GameManager.Instance.LoseLife(1);
        EnemyCounter.OnLeak();
        Destroy(gameObject);
    }

    // --- Targetability for camo ---
    public bool IsTargetableBy(Dragon owner)
    {
        if (def == null) return true;
        if (def.camo && owner != null && !owner.canDetectCamo) return false;
        return true;
    }

    // ========= PUBLIC CC/DEBUFF API =========

    public void ApplyStun(float duration)
    {
        if (duration <= 0f) return;
        if (stunRoutine != null) StopCoroutine(stunRoutine);
        stunRoutine = StartCoroutine(StunCo(duration));
    }

    IEnumerator StunCo(float duration)
    {
        stunned = true;
        yield return new WaitForSeconds(duration);
        stunned = false;
        stunRoutine = null;
    }

    /// <summary>
    /// Applies one stack of armor shred: increases damage taken by 'pct' for 'duration' seconds.
    /// Stacks additively and expire independently.
    /// </summary>
    public void ApplyArmorShred(float pct, float duration)
    {
        if (pct <= 0f || duration <= 0f) return;

        // First application sets the per-stack value; later calls can upgrade it if higher.
        shredPctPerStack = Mathf.Max(shredPctPerStack, pct);

        // Add a stack (capped), and attach an expiry coroutine to remove it.
        if (shredStacks < shredMaxStacks)
        {
            shredStacks++;
            var co = StartCoroutine(RemoveShredAfter(duration));
            shredCoroutines.Add(co);
        }
        else
        {
            // If capped, refresh one stack by removing the oldest and re-adding
            if (shredCoroutines.Count > 0)
            {
                StopCoroutine(shredCoroutines[0]);
                shredCoroutines.RemoveAt(0);
                var co = StartCoroutine(RemoveShredAfter(duration));
                shredCoroutines.Add(co);
            }
        }
    }

    IEnumerator RemoveShredAfter(float duration)
    {
        yield return new WaitForSeconds(duration);
        shredStacks = Mathf.Max(0, shredStacks - 1);
        // (We don't strictly need to prune the coroutine list here.)
    }
}

// Keep enum with the same names AND include the legacy 'Generic' default.
public enum DamageType
{
    Generic = 0,   // used by callers that don’t specify; treated as no extra resistance
    Physical = 1,
    Fire = 2,
    Ice = 3,
    Lightning = 4,
    Egg = 5,
    Crystal = 6
}

}
