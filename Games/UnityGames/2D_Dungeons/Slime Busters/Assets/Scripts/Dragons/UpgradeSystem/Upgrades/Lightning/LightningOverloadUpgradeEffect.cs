using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Lightning/Overload", fileName = "FX_Lightning_Overload")]
public class LightningOverloadUpgradeEffect : UpgradeEffectSO
{
    [Header("Auto Overload (T1/T2)")]
    public bool enableOverload = false;
    [Min(1)] public int threshold = 10;
    [Tooltip("Explosion radius around the hit that triggers overload.")]
    public float aoeRadius = 0.6f;
    [Tooltip("AOE damage as a fraction of the triggering hit (0.5 = 50%).")]
    public float aoeDamageMult = 0.5f;

    [Header("Manual Thunderburst (T3)")]
    public bool enableManualDischarge = false;
    [Min(0.1f)] public float manualCooldown = 9f;
    [Min(0)] public int manualRadialHops = 6;
    [Min(0.1f)] public float manualRadialRadius = 2.5f;
    [Tooltip("Damage fraction per spoke hop (0.7 = 70% of base).")]
    public float manualDamageMult = 0.7f;

    public override void Apply(Dragon d)
    {
        var la = d.attack as LightningAttack;
        if (!la) { Debug.LogWarning("LightningOverloadUpgradeEffect: Dragon has no LightningAttack.", d); return; }

        if (enableOverload)
            la.EnableOverload(true, threshold, aoeRadius, aoeDamageMult);

        if (enableManualDischarge)
            la.EnableManualDischarge(manualCooldown, manualRadialHops, manualRadialRadius, manualDamageMult);
    }

    public override void Remove(Dragon d) { }
}
