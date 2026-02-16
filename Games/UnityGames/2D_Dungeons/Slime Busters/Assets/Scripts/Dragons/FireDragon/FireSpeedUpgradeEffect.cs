using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Fire/Speed Upgrade", fileName = "FX_Fire_Speed")]
public class FireSpeedUpgradeEffect : UpgradeEffectSO
{
    [Header("Burst cadence")]
    [Tooltip("Multiply burst cooldown. 0.9 = 10% faster. 0.6 = 40% faster.")]
    public float cooldownMult = 0.9f;

    [Tooltip("Override time between shots inside a burst. -1 = don't change.")]
    public float intraShotDelayOverride = -1f;

    [Tooltip("Add bullets per burst (can be 0).")]
    public int addBulletsPerBurst = 0;

    public override void Apply(Dragon d)
    {
        var fa = d.attack as FireAttack;
        if (!fa) { Debug.LogWarning("FireSpeedUpgradeEffect: target has no FireAttack.", d); return; }

        if (cooldownMult > 0f) fa.MulCooldown(cooldownMult);
        if (intraShotDelayOverride >= 0f) fa.SetIntraShotDelay(intraShotDelayOverride);
        if (addBulletsPerBurst != 0) fa.AddBulletsPerBurst(addBulletsPerBurst);
    }

    public override void Remove(Dragon d)
    {
        // no-op (you can implement reversal if you add respec/sell-back of upgrades)
    }
}
