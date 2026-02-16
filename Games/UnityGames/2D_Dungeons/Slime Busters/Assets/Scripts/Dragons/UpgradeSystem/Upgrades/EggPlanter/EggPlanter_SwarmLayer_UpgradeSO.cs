using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/EggPlanter/Swarm", fileName = "FX_Egg_Swarm")]
public class EggPlanterSwarmEffect : UpgradeEffectSO
{
    [Header("Quantity / Cadence")]
    public int eggsPerCycleDelta = 0;       // +1, +2, etc.
    public float plantCooldownMult = 1f;    // 0.8 = faster
    public int capDelta = 0;                // +12, etc.

    [Header("Egg Stats")]
    public float damageMult = 1f;           // 0.8 etc.
    public float lifetimeMult = 1f;         // 1.3 etc.
    public float blastRadiusMult = 1f;      // 0.9 etc.

    public override void Apply(Dragon d)
    {
        var atk = FindEggPlanter(d);
        if (!atk) return;

        if (eggsPerCycleDelta != 0) atk.AddEggsPerCycle(eggsPerCycleDelta);
        if (!Mathf.Approximately(plantCooldownMult, 1f)) atk.MulPlantCooldown(plantCooldownMult);
        if (capDelta != 0) atk.AddEggCap(capDelta);

        if (!Mathf.Approximately(damageMult, 1f)) atk.MulEggDamage(damageMult);
        if (!Mathf.Approximately(lifetimeMult, 1f)) atk.MulEggLifetime(lifetimeMult);
        if (!Mathf.Approximately(blastRadiusMult, 1f)) atk.MulBlastRadius(blastRadiusMult);
    }

    EggPlanterAttack FindEggPlanter(Dragon d)
    {
        if (!d) { Debug.LogWarning("EggPlanterSwarmEffect.Apply: null Dragon."); return null; }
        var atk = d.attack as EggPlanterAttack
               ?? d.GetComponent<EggPlanterAttack>()
               ?? d.GetComponentInChildren<EggPlanterAttack>(true);
        if (!atk) Debug.LogWarning("EggPlanterSwarmEffect: EggPlanterAttack not found on Dragon.", d);
        return atk;
    }


    public override void Remove(Dragon d) { }
}
