using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Ice/Aura Upgrade", fileName = "FX_Ice_Aura")]
public class IceAuraUpgradeEffect : UpgradeEffectSO
{
    [Header("Aura Settings")]
    public bool enableAura = true;
    public float auraRadius = 2.25f;
    [Range(0f, 1f)] public float auraSlowPct = 0.25f;
    public float auraSlowDur = 0.75f;
    public float tickInterval = 0.25f;

    [Header("Minor Breath Tweaks (optional)")]
    public bool tweakBreathSlow;
    [Range(0f, 1f)] public float breathSlowPct = 0.45f;
    public float breathSlowDur = 1.8f;

    public override void Apply(Dragon d)
    {
        var ia = d.attack as IceAttack;
        if (!ia)
        {
            Debug.LogWarning("IceAuraUpgradeEffect applied to non-Ice dragon.", d);
            return;
        }

        if (enableAura) ia.EnableAura(auraRadius, auraSlowPct, auraSlowDur, tickInterval);
        if (tweakBreathSlow) ia.SetBaseSlow(breathSlowPct, breathSlowDur);
    }

    public override void Remove(Dragon d) { }
}
