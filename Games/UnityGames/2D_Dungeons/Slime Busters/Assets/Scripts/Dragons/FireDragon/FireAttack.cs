using System.Collections;
using UnityEngine;
using SlimeBusters;

public class FireAttack : AttackBehaviour
{
    // We keep a simple "mode" just for clarity. MachineGun is just very fast Burst.
    private enum Mode { Burst, Explosive }
    [SerializeField] Mode mode = Mode.Burst;

    [Header("Setup")]
    [SerializeField] GameObject bulletPrefab;  // MUST have FireBullet
    [SerializeField] float projectileSpeed = 10f;

    [Header("Burst cadence")]
    [SerializeField] int bulletsPerBurst = 3;     // pellets per burst
    [SerializeField] float intraShotDelay = 0.08f; // delay between pellets in a burst
    [SerializeField] float baseBurstCooldown = 1.60f; // time between bursts BEFORE fireRate multiplier

    [Header("Splash / Burn (0 = off)")]
    [SerializeField] float splashRadius = 0f;
    [SerializeField] float burnDps = 0f;
    [SerializeField] float burnDuration = 0f;

    [Header("Pierce (0 = off)")]
    [SerializeField] int pierceCount = 0;

    bool isOnCooldown;

    public override bool RequiresTarget => true;

    public override void Bind(Dragon d)
    {
        base.Bind(d);
        isOnCooldown = false;
    }

    public override void Tick(float dt) { }

    public override bool CanFireNow() => !isOnCooldown;

    float EffectiveBurstCooldown()
    {
        // higher owner.fireRate => faster firing (divide cooldown)
        float mult = Mathf.Max(0.01f, owner ? owner.fireRate : 1f);
        return baseBurstCooldown / mult;
    }

    public override void Fire(Vector3 origin, Enemy target, Dragon owner)
    {
        if (isOnCooldown || target == null || bulletPrefab == null) return;
        owner.StartCoroutine(FireBurst(origin, target, owner));
    }

    IEnumerator FireBurst(Vector3 origin, Enemy target, Dragon owner)
    {
        isOnCooldown = true;

        for (int i = 0; i < bulletsPerBurst; i++)
        {
            if (target == null) break;

            var go = Object.Instantiate(bulletPrefab, origin, Quaternion.identity);
            var b = go.GetComponent<FireBullet>(); // prefab MUST have it

            if (b != null)
            {
                b.Init(
                    target: target.transform,
                    damage: owner.damage,
                    speed: projectileSpeed,
                    splashRadius: (mode == Mode.Explosive ? Mathf.Max(0f, splashRadius) : 0f),
                    burnDps: (mode == Mode.Explosive ? Mathf.Max(0f, burnDps) : 0f),
                    burnDuration: (mode == Mode.Explosive ? Mathf.Max(0f, burnDuration) : 0f),
                    pierce: Mathf.Max(0, pierceCount),
                    mask: owner.enemyMask
                );
            }

            if (i < bulletsPerBurst - 1 && intraShotDelay > 0f)
                yield return new WaitForSeconds(intraShotDelay);
        }

        yield return new WaitForSeconds(EffectiveBurstCooldown());
        isOnCooldown = false;
    }

    // -------- Helpers called by your UpgradeEffectSOs --------

    // SPEED path
    public void MulCooldown(float mult) { baseBurstCooldown = Mathf.Max(0.05f, baseBurstCooldown * Mathf.Max(0.01f, mult)); }
    public void SetIntraShotDelay(float seconds) { intraShotDelay = Mathf.Max(0f, seconds); }
    public void AddBulletsPerBurst(int add) { bulletsPerBurst = Mathf.Max(1, bulletsPerBurst + add); }

    // PIERCE/DAMAGE path  (damage is on Dragon; pierce handled here)
    public void SetPierceAtLeast(int min) { pierceCount = Mathf.Max(pierceCount, min); }

    // SPLASH/BURN path
    public void SetSplashAtLeast(float radius) { splashRadius = Mathf.Max(splashRadius, radius); mode = Mode.Explosive; }
    public void AddBurnDps(float add) { burnDps = Mathf.Max(0f, burnDps + add); mode = Mode.Explosive; }
    public void SetBurnDurationAtLeast(float s) { burnDuration = Mathf.Max(burnDuration, s); mode = Mode.Explosive; }

    // Optional explicit switches (usually not needed; splash/burn setters already switch)
    public void SwitchModeToExplosive() { mode = Mode.Explosive; }
    public void SwitchModeToBurst() { mode = Mode.Burst; splashRadius = 0f; burnDps = 0f; burnDuration = 0f; }
}
