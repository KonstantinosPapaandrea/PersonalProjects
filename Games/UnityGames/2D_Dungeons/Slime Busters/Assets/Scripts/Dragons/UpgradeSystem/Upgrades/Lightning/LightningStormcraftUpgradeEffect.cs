using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Lightning/Stormcraft", fileName = "FX_Lightning_Stormcraft")]
public class LightningStormcraftUpgradeEffect : UpgradeEffectSO
{
    [Header("Rod deploy (T1)")]
    public bool enableRodDeploy = false;
    [Min(0.1f)] public float rodCooldown = 12f;
    [Min(0.1f)] public float rodLifetime = 6f;
    [Min(0f)] public float rodZapDps = 2f;

    [Header("Dragon static field (T2)")]
    public bool enableDragonAura = false;
    [Min(0.1f)] public float dragonAuraRadius = 1.2f;
    [Min(0f)] public float dragonAuraDps = 3f;

    [Header("Rod upgrades (T3)")]
    public bool rodsPermanent = false;
    public bool enableRodAura = false;
    [Min(0.1f)] public float rodAuraRadius = 1.0f;
    [Min(0f)] public float rodAuraDps = 2f;

    public override void Apply(Dragon d)
    {
        var la = d.attack as LightningAttack;
        if (!la) { Debug.LogWarning("LightningStormcraftUpgradeEffect: Dragon has no LightningAttack.", d); return; }

        if (enableRodDeploy)
            la.EnableRodDeploy(rodCooldown, rodLifetime, rodZapDps);

        if (enableDragonAura)
            la.EnableDragonAura(dragonAuraRadius, dragonAuraDps);

        la.RodsPermanent(rodsPermanent);

        if (enableRodAura)
            la.EnableRodAura(true, rodAuraRadius, rodAuraDps);
    }

    public override void Remove(Dragon d) { }
}
