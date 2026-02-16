using System.Collections.Generic;
using UnityEngine;
using SlimeBusters;

public class IceAttack : AttackBehaviour
{
    [Header("Gameplay Cone (base)")]
    [Tooltip("Degrees wide for hit/slow checks (gameplay only).")]
    [SerializeField] float gameplayConeAngle = 35f;
    [SerializeField] float coneRange = 2.75f;

    [Header("Base Slow (always-on breath)")]
    [SerializeField, Range(0f, 1f)] float slowPercent = 0.40f;
    [SerializeField] float slowDuration = 1.75f;
    [SerializeField] int damage = 0; // Utility tower: set very low or 0

    [Header("Cadence")]
    [SerializeField] float fireCooldown = 0.45f;
    bool onCd;

    [Header("VFX (optional)")]
    public ParticleSystem iceBreathFX;
    public bool syncVFXToGameplay = true;

    // ================== UPGRADE FLAGS / PARAMS ==================

    // A) Extra Freeze/Stun (Path A)
    bool freezeEnabled;
    float freezeChance;     // 0..1
    float freezeDuration;   // seconds

    // Frozen ground patch (Path A optional)
    bool groundEnabled;
    GameObject groundPatchPrefab;
    float groundCooldown;
    float groundRadius;
    float groundDuration;
    float groundTimer;

    // B) Aura Control (Path B)
    bool auraEnabled;
    float auraRadius;
    float auraSlowPct;
    float auraSlowDur;
    float auraTickInterval = 0.25f;
    float auraTimer;

    // C) Shards (Path C – slight damage)
    bool shardsEnabled;
    GameObject shardPrefab;             // uses IceShard
    int shardCount = 0;
    float shardSpeed = 10f;
    float shardSpreadDeg = 18f;
    int shardDamage = 1;

    // Utility
    Transform AimRoot => owner && owner.rotateRoot ? owner.rotateRoot : (owner ? owner.transform : transform);

    public override bool RequiresTarget => true;

    public override void Bind(Dragon d)
    {
        base.Bind(d);
        onCd = false;
        groundTimer = 0f;
        auraTimer = 0f;
    }

    public override void Tick(float dt)
    {
        if (groundEnabled && groundTimer > 0f) groundTimer -= dt;
        if (auraEnabled)
        {
            auraTimer -= dt;
            if (auraTimer <= 0f)
            {
                auraTimer = Mathf.Max(0.05f, auraTickInterval);
                ApplyAuraTick();
            }
        }
    }

    public override bool CanFireNow() => !onCd;

    public override void Fire(Vector3 origin, Enemy target, Dragon owner)
    {
        if (onCd) return;

        // 1) Determine aim direction from the rotating root
        Transform aim = AimRoot;
        Vector2 forward = aim ? (Vector2)aim.right : Vector2.right;
        float half = gameplayConeAngle * 0.5f;

        // 2) Cone AA check
        var enemies = GameObject.FindObjectsOfType<Enemy>();
        List<Enemy> hitList = new List<Enemy>(16);

        foreach (var e in enemies)
        {
            if (!e) continue;
            Vector2 toEnemy = (Vector2)(e.transform.position - (aim ? aim.position : transform.position));
            float dist = toEnemy.magnitude;
            if (dist > coneRange) continue;
            float ang = Vector2.Angle(forward, toEnemy);
            if (ang <= half)
            {
                // Base breath: light damage + slow
                if (damage > 0) e.TakeDamage(damage,DamageType.Ice);
                if (slowPercent > 0f && slowDuration > 0f) e.ApplySlow(slowPercent, slowDuration);

                // Optional freeze
                if (freezeEnabled && freezeDuration > 0f && Random.value < Mathf.Clamp01(freezeChance))
                    e.ApplyStun(freezeDuration);

                hitList.Add(e);
            }
        }

        // 3) Ground patch spawn (at ~70% of range along facing dir)
        if (groundEnabled && groundPatchPrefab && groundTimer <= 0f)
        {
            groundTimer = Mathf.Max(0.05f, groundCooldown);
            Vector3 center = (aim ? aim.position : transform.position) + (Vector3)(forward.normalized * (coneRange * 0.7f));
            var go = Instantiate(groundPatchPrefab, center, Quaternion.identity);
            var gp = go.GetComponent<IceGroundPatch>();
            if (gp)
            {
                gp.Configure(auraSlowPct: slowPercent, auraSlowDur: slowDuration, radius: groundRadius, life: groundDuration);
            }
        }

        // 4) Shards (slight damage path) – fire straight fan in aim direction
        if (shardsEnabled && shardPrefab && shardCount > 0)
        {
            float start = -shardSpreadDeg * 0.5f;
            float step = shardCount > 1 ? (shardSpreadDeg / (shardCount - 1)) : 0f;

            for (int i = 0; i < shardCount; i++)
            {
                float z = start + step * i;
                Quaternion rot2D = Quaternion.AngleAxis(z, Vector3.forward) * Quaternion.FromToRotation(Vector3.right, new Vector3(forward.x, forward.y, 0f));
                var go = Instantiate(shardPrefab, origin, rot2D);
                var s = go.GetComponent<IceShard>();
                if (s) s.Init(direction: rot2D * Vector3.right, speed: shardSpeed, damage: shardDamage, slowPct: 0f, slowDur: 0f);
            }
        }

        // 5) VFX
        if (iceBreathFX)
        {
            iceBreathFX.transform.position = origin;
            Quaternion rot2D = Quaternion.FromToRotation(Vector3.right, new Vector3(forward.x, forward.y, 0f));
            iceBreathFX.transform.rotation = rot2D;

            var main = iceBreathFX.main;
            main.simulationSpace = ParticleSystemSimulationSpace.World;

            iceBreathFX.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            iceBreathFX.Play();
        }

        // 6) Cooldown
        owner.StartCoroutine(CoFireCooldown());
    }

    System.Collections.IEnumerator CoFireCooldown()
    {
        onCd = true;
        float mult = Mathf.Max(0.01f, owner ? owner.fireRate : 1f);
        yield return new WaitForSeconds(fireCooldown / mult);
        onCd = false;
    }

    void ApplyAuraTick()
    {
        if (!owner) return;
        var pos = owner.transform.position;
        var hits = Physics2D.OverlapCircleAll(pos, auraRadius, owner.enemyMask);
        foreach (var h in hits)
        {
            var e = h.GetComponent<Enemy>();
            if (!e) continue;
            if (auraSlowPct > 0f && auraSlowDur > 0f) e.ApplySlow(auraSlowPct, auraSlowDur);
        }
    }

    void OnDrawGizmosSelected()
    {
        Gizmos.color = new Color(0, 0.7f, 1f, 0.18f);
        Vector3 origin = transform.position;
        Vector3 forward = transform.right;
        int seg = 20;
        float half = gameplayConeAngle * 0.5f;
        Vector3 prev = origin;
        for (int i = 0; i <= seg; i++)
        {
            float ang = -half + (gameplayConeAngle * i / seg);
            Vector3 dir = Quaternion.Euler(0, 0, ang) * forward;
            Vector3 end = origin + dir.normalized * coneRange;
            Gizmos.DrawLine(origin, end);
            if (i > 0) Gizmos.DrawLine(prev, end);
            prev = end;
        }

        if (auraEnabled)
        {
            Gizmos.color = new Color(0.5f, 0.9f, 1f, 0.15f);
            Gizmos.DrawWireSphere(origin, auraRadius);
        }
    }

    // ================== UPGRADE HOOKS ==================

    public void SetBaseSlow(float pct, float dur) { slowPercent = Mathf.Clamp01(pct); slowDuration = Mathf.Max(0f, dur); }
    public void SetCone(float angle, float range) { gameplayConeAngle = Mathf.Max(1f, angle); coneRange = Mathf.Max(0.25f, range); }
    public void SetBaseDamage(int dmg) { damage = Mathf.Max(0, dmg); }
    public void SetFireCooldown(float s) { fireCooldown = Mathf.Max(0.05f, s); }

    // Path A — Freeze & ground
    public void EnableFreeze(float chance, float duration)
    {
        freezeEnabled = true;
        freezeChance = Mathf.Clamp01(chance);
        freezeDuration = Mathf.Max(0f, duration);
    }
    public void EnableFrozenGround(GameObject patchPrefab, float cooldown, float radius, float duration)
    {
        groundEnabled = true;
        groundPatchPrefab = patchPrefab;
        groundCooldown = Mathf.Max(0.1f, cooldown);
        groundRadius = Mathf.Max(0.25f, radius);
        groundDuration = Mathf.Max(0.1f, duration);
        groundTimer = 0f;
    }

    // Path B — Aura
    public void EnableAura(float radius, float slowPct, float slowDur, float tickInterval = 0.25f)
    {
        auraEnabled = true;
        auraRadius = Mathf.Max(0.25f, radius);
        auraSlowPct = Mathf.Clamp01(slowPct);
        auraSlowDur = Mathf.Max(0f, slowDur);
        auraTickInterval = Mathf.Max(0.05f, tickInterval);
        auraTimer = 0f;
    }

    // Path C — Shards (slight damage)
    public void EnableShards(GameObject prefab, int count, float speed, float spreadDeg, int dmgPerShard)
    {
        shardsEnabled = true;
        shardPrefab = prefab;
        shardCount = Mathf.Max(0, count);
        shardSpeed = Mathf.Max(0.1f, speed);
        shardSpreadDeg = Mathf.Max(0f, spreadDeg);
        shardDamage = Mathf.Max(0, dmgPerShard);
    }
}
