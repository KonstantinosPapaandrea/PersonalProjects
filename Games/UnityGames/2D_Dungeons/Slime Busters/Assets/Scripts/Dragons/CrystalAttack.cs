using System.Collections;
using UnityEngine;
using SlimeBusters;

public class CrystalAttack : AttackBehaviour
{
    [Header("Projectile")]
    [SerializeField] float projectileSpeed = 14f;   // base sniper speed

    [Header("Cadence")]
    [SerializeField] float baseShotCooldown = 1.25f; // time between shots BEFORE owner.fireRate multiplier
    [SerializeField] float intraMultiDelay = 0.06f; // delay between multi-shot pellets

    // ------- DAMAGE / PIERCE -------
    int pierceMin = 0;

    // Armor shred (optional debuff)
    bool armorShredEnabled = false;
    float armorShredPercent = 0f;   // e.g., 0.15f = -15% armor / +15% dmg taken
    float armorShredDuration = 0f;

    // ------- RAPID / BURST -------
    int extraShotsEveryN = 0; // e.g., 1 extra shot every 3rd trigger
    int triggerCount = 0;
    int multiShotCount = 0; // e.g., 3 = fire 3 pellets per trigger

    // ------- CONTROL -------
    // slow on hit
    bool slowEnabled = false;
    float slowPercent = 0f;   // 0.2 = 20%
    float slowDuration = 0f;

    // stun on hit
    bool stunEnabled = false;
    float stunDuration = 0f;

    // periodic prison shot (long stun/freeze)
    bool prisonEnabled = false;
    float prisonCooldown = 0f;
    float prisonDuration = 0f;
    float prisonCdTimer = 0f;

    // internal cooldown
    bool isOnCooldown = false;

    public override bool RequiresTarget => true;

    public override void Bind(Dragon d)
    {
        base.Bind(d);
        isOnCooldown = false;
        prisonCdTimer = 0f;
    }

    public override void Tick(float dt)
    {
        if (prisonEnabled && prisonCdTimer > 0f)
            prisonCdTimer -= dt;
    }

    public override bool CanFireNow() => !isOnCooldown;

    float EffectiveCooldown()
    {
        // Higher owner.fireRate => faster shooting
        float mult = Mathf.Max(0.01f, owner ? owner.fireRate : 1f);
        return baseShotCooldown / mult;
    }

    public override void Fire(Vector3 origin, Enemy target, Dragon owner)
    {
        if (isOnCooldown || target == null || bulletPrefab == null) return;
        owner.StartCoroutine(FireSequence(origin, target, owner));
    }

    IEnumerator FireSequence(Vector3 origin, Enemy target, Dragon owner)
    {
        isOnCooldown = true;

        // Determine prison bolt for THIS trigger
        bool usePrisonThisTrigger = prisonEnabled && prisonCdTimer <= 0f;
        if (usePrisonThisTrigger) prisonCdTimer = prisonCooldown;

        // How many pellets in this trigger?
        int pellets = Mathf.Max(1, multiShotCount > 0 ? multiShotCount : 1);

        // Extra shot every N triggers?
        triggerCount++;
        if (extraShotsEveryN > 0 && (triggerCount % extraShotsEveryN) == 0)
            pellets += 1;

        for (int i = 0; i < pellets; i++)
        {
            if (!target) break;

            var go = Object.Instantiate(bulletPrefab, origin, Quaternion.identity);
            var b = go.GetComponent<CrystalBullet>(); // prefab MUST have CrystalBullet
            if (b != null)
            {
                // Extended init carrying debuffs & control
                b.Init(
                    target: target.transform,
                    damage: owner.damage,
                    speed: projectileSpeed,
                    pierce: pierceMin,
                    mask: owner.enemyMask,
                    // control/debuffs
                    slowPercent: slowEnabled ? slowPercent : 0f,
                    slowDuration: slowEnabled ? slowDuration : 0f,
                    stunDuration: stunEnabled ? stunDuration : 0f,
                    armorShredPct: armorShredEnabled ? armorShredPercent : 0f,
                    armorShredDur: armorShredEnabled ? armorShredDuration : 0f,
                    prisonStunDur: (usePrisonThisTrigger && i == 0) ? prisonDuration : 0f // first pellet becomes Prison bolt
                );
            }

            if (i < pellets - 1 && intraMultiDelay > 0f)
                yield return new WaitForSeconds(intraMultiDelay);
        }

        yield return new WaitForSeconds(EffectiveCooldown());
        isOnCooldown = false;
    }

    // ========== Hooks for UpgradeEffectSOs ==========

    // DAMAGE / PIERCE
    public void SetPierceAtLeast(int min) { pierceMin = Mathf.Max(pierceMin, min); }
    public void EnableArmorShred(float pct, float dur)
    {
        armorShredEnabled = true;
        armorShredPercent = Mathf.Max(0f, pct);
        armorShredDuration = Mathf.Max(0f, dur);
    }

    // RAPID
    public void EnableExtraShots(int everyN) { extraShotsEveryN = Mathf.Max(0, everyN); }
    public void EnableMultiShot(int count) { multiShotCount = Mathf.Max(0, count); }
    public void SetBaseCooldown(float seconds) { baseShotCooldown = Mathf.Max(0.05f, seconds); }
    public void SetIntraMultiDelay(float s) { intraMultiDelay = Mathf.Max(0f, s); }

    // CONTROL
    public void EnableSlow(float pct, float dur)
    {
        slowEnabled = true;
        slowPercent = Mathf.Clamp01(pct);
        slowDuration = Mathf.Max(0f, dur);
    }
    public void EnableStun(float dur)
    {
        stunEnabled = true;
        stunDuration = Mathf.Max(0f, dur);
    }
    public void EnablePrisonShot(float cooldown, float duration)
    {
        prisonEnabled = true;
        prisonCooldown = Mathf.Max(0.1f, cooldown);
        prisonDuration = Mathf.Max(0f, duration);
        prisonCdTimer = 0f; // ready immediately
    }
}
