using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Lightning/Chain Mastery", fileName = "FX_Lightning_Chain")]
public class LightningChainUpgradeEffect : UpgradeEffectSO
{
    [Header("Chain")]
    [Tooltip("Add this many extra jumps to the chain (can be 0).")]
    public int addExtraJumps = 0;

    [Tooltip("Multiply chain radius (1.15 = +15%). 1 = no change.")]
    public float chainRadiusMult = 1f;

    [Tooltip("Per-hop damage multiplier (0.9 = -10% per hop). < 0 to leave unchanged.")]
    public float falloffPerHop = -1f;

    [Tooltip("Prefer not to hit already zapped enemies within the same chain.")]
    public bool? preferUnhitTargets = null;

    [Header("Multi-bolts per shot")]
    [Tooltip("Set bolts fired per attack (1..3). 0 = do not change.")]
    [Range(0, 3)] public int setBoltsPerShot = 0;

    public override void Apply(Dragon d)
    {
        var la = d.attack as LightningAttack;
        if (!la) { Debug.LogWarning("LightningChainUpgradeEffect: Dragon has no LightningAttack.", d); return; }

        if (addExtraJumps != 0) la.AddExtraJumps(addExtraJumps);
        if (!Mathf.Approximately(chainRadiusMult, 1f)) la.MulChainRadius(chainRadiusMult);
        if (falloffPerHop >= 0f) la.SetFalloffPerHop(falloffPerHop);
        if (preferUnhitTargets.HasValue) la.PreferUnhitTargets(preferUnhitTargets.Value);
        if (setBoltsPerShot >= 1) la.SetBoltsPerShot(Mathf.Clamp(setBoltsPerShot, 1, 3));
    }

    public override void Remove(Dragon d) { /* no-op (add reversal if you support respec) */ }
}
