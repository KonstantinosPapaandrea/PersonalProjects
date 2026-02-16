using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Tilemaps;
using SlimeBusters;

public class LightningAttack : AttackBehaviour, ILightningHitSink
{
    [Header("Cadence")]
    [SerializeField] float baseCooldown = 1.0f;        // BEFORE owner.fireRate multiplier
    [SerializeField] float projectileSpeed = 12f;       // first bolt flight speed

    [Header("Chain Core")]
    [SerializeField] int baseJumps = 5;               // enemies after the first
    [SerializeField] float chainRadius = 2.8f;
    [Range(0.1f, 1f)][SerializeField] float falloffPerHop = 0.85f; // damage *= falloff each hop
    [SerializeField] bool preferUnhitTargets = true;    // avoid already-hit enemies in this chain

    [Header("Visuals (pass to bullet)")]
    public Material arcMaterial;
    public float arcWidth = 0.08f;
    public float arcLifetime = 0.10f;
    public int jaggedPoints = 10;

    // Path A: multi-bolts per attack
    int boltsPerShot = 1; // 1 (base), 2 (T2), 3 (T3)

    // Path B: Overload
    bool overloadEnabled = false;
    int overloadStacks = 0;
    int overloadThreshold = 10;
    float overloadAoERadius = 0.6f;
    float overloadAoEDmgMult = 0.5f; // % of current hit damage
    float manualDischargeCd = 0f, manualDischargeTimer = 0f;
    int manualRadialHops = 6;
    float manualRadialRadius = 2.5f;
    float manualRadialDmgMult = 0.7f;

    // Path C: Stormcraft auras/rods
    bool dragonAuraOn = false;
    float dragonAuraRadius = 0f;
    float dragonAuraDps = 0f;
    Coroutine dragonAuraCo;

    bool rodsPermanent = false;
    bool rodAuraOn = false; float rodAuraRadius = 0.9f; float rodAuraDps = 2f;
    bool rodDeployEnabled = false;
    float rodCooldown = 12f, rodLifetime = 6f, rodZapDps = 2f;
    float rodTimer = 0f;
    public GameObject rodPrefab; // optional; if null well create one
                                 // add near your rod fields
    float nextRodTime = 0f; // absolute deadline (Time.time) when a rod may spawn again

    bool onCd = false;

    // ================== Hotspot auto-deploy (NEW) ==================
    [Header("Auto Rod Placement (Hotspot)")]
    [SerializeField] bool autoDeployRods = true;   // turn on to auto-place
    [SerializeField] float autoCheckEvery = 0.6f;  // seconds between checks
    [SerializeField] int recentHitsMax = 12;       // memory size for centroid
    [SerializeField] float maxHotspotDistance = 4.0f; // clamp from dragon to avoid far-off placements
    [SerializeField] bool snapRodToRoad = true;    // snap to tilemap if available

    float autoTimer = 0f;
    readonly Queue<Vector3> recentHits = new Queue<Vector3>(16);

    // optional scene ref; will auto-find if null
    [SerializeField] Tilemap roadMap;

    public override bool RequiresTarget => true;

    public override void Bind(Dragon d)
    {
        
            base.Bind(d);
            onCd = false;
            manualDischargeTimer = 0f;
            if (dragonAuraOn && dragonAuraCo == null) dragonAuraCo = StartCoroutine(DragonAuraTick());

            // Auto-find road tilemap (tag, name, or provider) if snapping is desired
            if (!roadMap && snapRodToRoad)
        {
            if (RoadMapProvider.Instance) roadMap = RoadMapProvider.Instance.tilemap;
            if (!roadMap)
            {
                var tagged = GameObject.FindWithTag("RoadTilemap");
                if (tagged) roadMap = tagged.GetComponent<Tilemap>();
            }
            if (!roadMap)
            {
                var named = GameObject.Find("Road");
                if (named) roadMap = named.GetComponent<Tilemap>();
            }
        }
        // ---- ensure predictable timers ----
        rodCooldown = Mathf.Max(0.1f, rodCooldown);
        rodLifetime = Mathf.Max(0.5f, rodLifetime);
        nextRodTime = Time.time; // allow immediate placement if logic wants it
        rodTimer = 0f;           // keep for UI/debug
        autoTimer = 0f;          // run the auto check right away
    }

    public override void Tick(float dt)
    {
        if (manualDischargeTimer > 0f) manualDischargeTimer -= dt;

        // derive rodTimer from absolute time (works even if Tick is sporadic)
        float remaining = nextRodTime - Time.time;
        rodTimer = Mathf.Max(0f, remaining);

        // ========= Auto-deploy loop =========
        autoTimer -= dt;
        if (autoDeployRods && rodDeployEnabled && Time.time >= nextRodTime && autoTimer <= 0f)
        {
            autoTimer = Mathf.Max(0.1f, autoCheckEvery);
            TryAutoDeployRod_Hotspot(); // will set nextRodTime on success
        }
    }


    public override bool CanFireNow() => !onCd;

    float EffectiveCd()
    {
        float mult = Mathf.Max(0.01f, owner ? owner.fireRate : 1f);
        return baseCooldown / mult;
    }

    public override void Fire(Vector3 origin, Enemy target, Dragon owner)
    {
        if (onCd || target == null || bulletPrefab == null) return;
        owner.StartCoroutine(FireSequence(origin, target, owner));
    }

    IEnumerator FireSequence(Vector3 origin, Enemy target, Dragon owner)
    {
        onCd = true;

        int count = Mathf.Max(1, boltsPerShot);
        for (int i = 0; i < count; i++)
        {
            if (!target) break;

            var go = Instantiate(bulletPrefab, origin, Quaternion.identity);
            var bolt = go.GetComponent<LightningBullet>();
            if (bolt == null) bolt = go.AddComponent<LightningBullet>(); // safety

            bolt.Init(
                firstTarget: target.transform,
                damage: owner.damage,
                speed: projectileSpeed,
                extraJumps: baseJumps,
                radius: chainRadius,
                falloffPerHop: falloffPerHop,
                preferUnhit: preferUnhitTargets,
                mask: owner.enemyMask,
                sink: this, // report hits for overload + hotspot memory
                arcMaterial: arcMaterial,
                arcWidth: arcWidth,
                arcLifetime: arcLifetime,
                jaggedPoints: jaggedPoints
            );
        }

        // optional: you could deploy on shot, but hotspot does it automatically
        // if (rodDeployEnabled && rodTimer <= 0f) { DeployRod(origin); }

        yield return new WaitForSeconds(EffectiveCd());
        onCd = false;
    }

    // =============== PATH A (Chain / Multi-bolts) HOOKS ===============
    public void AddExtraJumps(int add) { baseJumps = Mathf.Max(0, baseJumps + add); }
    public void MulChainRadius(float mult) { chainRadius = Mathf.Max(0.1f, chainRadius * Mathf.Max(0.01f, mult)); }
    public void SetFalloffPerHop(float f) { falloffPerHop = Mathf.Clamp01(Mathf.Max(0.01f, f)); }
    public void PreferUnhitTargets(bool on) { preferUnhitTargets = on; }
    public void SetBoltsPerShot(int count) { boltsPerShot = Mathf.Clamp(count, 1, 3); }

    // =============== PATH B (Overload) HOOKS & LOGIC =================
    public void EnableOverload(bool on, int threshold, float aoeRadius, float aoeDmgMult)
    {
        overloadEnabled = on;
        overloadThreshold = Mathf.Max(1, threshold);
        overloadAoERadius = Mathf.Max(0.01f, aoeRadius);
        overloadAoEDmgMult = Mathf.Max(0f, aoeDmgMult);
        overloadStacks = 0;
    }

    public void EnableManualDischarge(float cooldown, int radialHops, float radialRadius, float dmgMult)
    {
        manualDischargeCd = Mathf.Max(0.1f, cooldown);
        manualDischargeTimer = 0f;
        manualRadialHops = Mathf.Max(0, radialHops);
        manualRadialRadius = Mathf.Max(0.1f, radialRadius);
        manualRadialDmgMult = Mathf.Max(0f, dmgMult);
    }

    // call this from a UI button to force discharge at current target (if any)
    public void TryManualDischarge(Enemy currentTarget)
    {
        if (manualDischargeCd <= 0f) return;
        if (manualDischargeTimer > 0f) return;
        if (!currentTarget) return;

        manualDischargeTimer = manualDischargeCd;
        StartCoroutine(DoRadialDischarge(currentTarget.transform.position, owner.damage));
    }

    IEnumerator DoRadialDischarge(Vector3 center, float baseDamage)
    {
        // radial "chain burst": spawn N short chains in random directions
        int spokes = 6;
        for (int i = 0; i < spokes; i++)
        {
            var go = new GameObject("RadialChain");
            var lb = go.AddComponent<LightningBullet>();
            lb.InitRadialBurst(
                startPos: center,
                damage: Mathf.RoundToInt(baseDamage * manualRadialDmgMult),
                hops: manualRadialHops,
                radius: manualRadialRadius,
                falloffPerHop: falloffPerHop,
                mask: owner.enemyMask,
                sink: this,
                arcMaterial: arcMaterial,
                arcWidth: arcWidth,
                arcLifetime: arcLifetime,
                jaggedPoints: jaggedPoints
            );
        }
        yield return null;
    }

    // ILightningHitSink  called by LightningBullet on each hit
    public void OnLightningHit(Enemy e, int dealtDamage, Vector3 hitPos)
    {
        // ====== Hotspot memory (NEW) ======
        if (recentHits.Count >= recentHitsMax) recentHits.Dequeue();
        recentHits.Enqueue(hitPos);

        // ====== Overload logic (existing) ======
        if (!overloadEnabled) return;

        overloadStacks++;
        if (overloadStacks >= overloadThreshold)
        {
            overloadStacks = 0;
            // small AoE around the last hit
            var hits = Physics2D.OverlapCircleAll(hitPos, overloadAoERadius, owner.enemyMask);
            foreach (var h in hits)
            {
                var en = h.GetComponent<Enemy>();
                if (!en) continue;
                int aoe = Mathf.Max(1, Mathf.RoundToInt(dealtDamage * overloadAoEDmgMult));
                en.TakeDamage(aoe, DamageType.Lightning);
            }
        }
    }

    // =============== PATH C (Stormcraft: auras / rods) HOOKS =========
    public void EnableDragonAura(float radius, float dps)
    {
        dragonAuraOn = true;
        dragonAuraRadius = Mathf.Max(0.1f, radius);
        dragonAuraDps = Mathf.Max(0f, dps);
        if (dragonAuraCo == null) dragonAuraCo = StartCoroutine(DragonAuraTick());
    }

    IEnumerator DragonAuraTick()
    {
        var wait = new WaitForSeconds(0.25f);
        while (true)
        {
            if (dragonAuraOn && dragonAuraDps > 0f && owner != null)
            {
                var hits = Physics2D.OverlapCircleAll(owner.transform.position, dragonAuraRadius, owner.enemyMask);
                foreach (var h in hits)
                {
                    var e = h.GetComponent<Enemy>();
                    if (!e) continue;
                    int dmg = Mathf.Max(1, Mathf.RoundToInt(dragonAuraDps * 0.25f));
                    e.TakeDamage(dmg, DamageType.Lightning);
                }
            }
            yield return wait;
        }
    }

    public void EnableRodDeploy(float cooldown, float lifetime, float zapDps)
    {
        rodDeployEnabled = true;
        rodCooldown = Mathf.Max(0.1f, cooldown);
        rodLifetime = Mathf.Max(0.1f, lifetime);
        rodZapDps = Mathf.Max(0f, zapDps);
        rodTimer = 0f;
    }

    public void RodsPermanent(bool on) { rodsPermanent = on; }

    public void EnableRodAura(bool on, float radius, float dps)
    {
        rodAuraOn = on;
        rodAuraRadius = Mathf.Max(0.1f, radius);
        rodAuraDps = Mathf.Max(0f, dps);
    }

    // Optional: call this from a UI button or after a kill, etc.
    public void TryDeployRod(Vector3 pos)
    {
        if (!rodDeployEnabled) return;
        if (Time.time < nextRodTime) return;

        // schedule the next allowed time NOW, before instantiating (avoids double spawns)
        nextRodTime = Time.time + Mathf.Max(0.1f, rodCooldown);
        rodTimer = Mathf.Max(0.1f, rodCooldown);

        DeployRod(pos);
    }

    void DeployRod(Vector3 pos)
    {
        Debug.Log($"[Rod] spawn pos={pos} lifetime={rodLifetime:F3}s permanent={rodsPermanent}", this);

        GameObject go = rodPrefab ? Instantiate(rodPrefab, pos, Quaternion.identity)
                                  : new GameObject("LightningRod");
        var rod = go.GetComponent<LightningRod>() ?? go.AddComponent<LightningRod>();

        rod.Init(ownerMask: owner.enemyMask,
                 zapDps: rodZapDps,
                 zapInterval: 0.5f,
                 preferChains: true,
                 auraOn: rodAuraOn,
                 auraRadius: rodAuraRadius,
                 auraDps: rodAuraDps);

        float life = Mathf.Max(0.5f, rodLifetime);
        if (!rodsPermanent) Destroy(go, life);
    }


    // ================== Hotspot core (NEW) ==================
    void TryAutoDeployRod_Hotspot()
    {
        if (!owner) return;
        if (Time.time < nextRodTime) return;

        Vector3 chosenPos;
        if (recentHits.Count > 0)
        {
            Vector3 sum = Vector3.zero; int n = 0;
            foreach (var p in recentHits) { sum += p; n++; }
            chosenPos = (n > 0) ? sum / n : owner.transform.position;
            Vector3 fromDragon = chosenPos - owner.transform.position;
            if (fromDragon.sqrMagnitude > maxHotspotDistance * maxHotspotDistance)
                chosenPos = owner.transform.position + fromDragon.normalized * maxHotspotDistance;
        }
        else
        {
            // forward-path fallback
            Vector3 origin = owner.transform.position;
            Vector3 fwd = owner && owner.rotateRoot ? owner.rotateRoot.right : Vector3.right;
            chosenPos = origin + fwd.normalized * 1.6f;
        }

        if (snapRodToRoad && TrySnapToRoad(roadMap, chosenPos, out var snapped, 2))
            TryDeployRod(snapped);
        else
            TryDeployRod(chosenPos);
    }

    Vector3 ForwardRodPosition()
    {
        Vector3 origin = owner.transform.position;
        Vector3 fwd = owner && owner.rotateRoot ? owner.rotateRoot.right : Vector3.right;
        return origin + fwd.normalized * 1.6f; // small offset ahead of dragon
    }


    // Reusable snap helper
    public static bool TrySnapToRoad(Tilemap map, Vector3 world, out Vector3 snapped, int searchRadius = 2)
    {
        snapped = world;
        if (!map) return false;

        var cell = map.WorldToCell(world);
        if (map.HasTile(cell)) { snapped = map.GetCellCenterWorld(cell); return true; }

        bool found = false; float best = float.MaxValue; Vector3Int bestCell = cell;
        for (int r = 1; r <= Mathf.Max(1, searchRadius); r++)
        {
            for (int dx = -r; dx <= r; dx++)
                for (int dy = -r; dy <= r; dy++)
                {
                    var c = new Vector3Int(cell.x + dx, cell.y + dy, cell.z);
                    if (!map.HasTile(c)) continue;
                    float d = (map.GetCellCenterWorld(c) - world).sqrMagnitude;
                    if (d < best) { best = d; bestCell = c; found = true; }
                }
            if (found) break;
        }
        if (found) snapped = map.GetCellCenterWorld(bestCell);
        return found;
    }
}

// A tiny interface for hit callbacks (used by Overload & hotspot)
public interface ILightningHitSink
{
    void OnLightningHit(Enemy e, int dealtDamage, Vector3 hitPos);
}
