using SlimeBusters;
﻿using UnityEngine;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/EggPlanter/Apex", fileName = "FX_Egg_Apex")]
public class EggPlanterApexEffect : UpgradeEffectSO
{
    [Header("Power Focus")]
    public int eggsPerCycleDelta = 0;        // -1, etc. (clamped ≥1 in attack)
    public float damageMult = 1f;            // 1.6, then 1.4, etc.
    public float blastRadiusMult = 1f;       // 1.2 / 1.3…

    [Header("Fuse / Boss Bonus")]
    public float fuseSeconds = -1f;          // set ≥0 to apply (e.g., 0.25)
    public float vsBossMult = 1f;            // 1.3…

    [Header("Empower Every Nth Egg")]
    public int empoweredEveryN = 0;          // 6 = every 6th
    public float empoweredDamageMult = 3f;   // 3.0x
    public float empoweredRadiusMult = 1.6f; // 1.6x
    public bool empoweredIgnoreShields = true;
    public override void Apply(Dragon d)
    {
        var atk = FindEggPlanter(d);
        if (!atk) return;

        if (eggsPerCycleDelta != 0) atk.AddEggsPerCycle(eggsPerCycleDelta);
        if (!Mathf.Approximately(damageMult, 1f)) atk.MulEggDamage(damageMult);
        if (!Mathf.Approximately(blastRadiusMult, 1f)) atk.MulBlastRadius(blastRadiusMult);

        if (fuseSeconds >= 0f) atk.SetTriggerFuse(fuseSeconds);
        if (!Mathf.Approximately(vsBossMult, 1f)) atk.SetBossBonus(vsBossMult);

        if (empoweredEveryN > 0)
            atk.EnableEmpoweredEveryN(empoweredEveryN, empoweredDamageMult, empoweredRadiusMult, empoweredIgnoreShields);
    }

    EggPlanterAttack FindEggPlanter(Dragon d)
    {
        if (!d)
        {
            Debug.LogWarning("EggPlanterApexEffect.Apply: null Dragon target.");
            return null;
        }
        // 1) try the assigned attack reference
        var atk = d.attack as EggPlanterAttack;
        if (atk) return atk;
        // 2) try on the same GO
        atk = d.GetComponent<EggPlanterAttack>();
        if (atk) return atk;
        // 3) try children (prefab setups often keep attack scripts on child)
        atk = d.GetComponentInChildren<EggPlanterAttack>(true);
        if (atk) return atk;

        Debug.LogWarning("EggPlanterApexEffect: Could not find EggPlanterAttack on Dragon.", d);
        return null;
    }

    public override void Remove(Dragon d) { }
}
