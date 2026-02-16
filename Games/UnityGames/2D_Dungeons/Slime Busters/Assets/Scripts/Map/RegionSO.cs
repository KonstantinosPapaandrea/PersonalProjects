using System.Collections.Generic;
using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/RegionSO")]
public class RegionSO : ScriptableObject
{
    [Header("Identity")]
    public string regionId; // "fire", "ice", "lightning", "eggplanter", "crystal"

    [Header("Enemy Pools")]
    public List<SlimeDef> common = new();
    public SlimeDef fast;
    public SlimeDef tank;
    public SlimeDef boss;

    [Header("Scaling Curves (x = wave index starting at 1)")]
    public AnimationCurve hpMult = AnimationCurve.Linear(1, 1, 100, 8);
    public AnimationCurve speedMult = AnimationCurve.Linear(1, 1, 100, 1.35f);
    public AnimationCurve bountyMult = AnimationCurve.Linear(1, 1, 100, 3f);

    [Header("Resistance Bonus (all elemental types)")]
    public AnimationCurve resistBonusAll; // y in [0..100]; optional
}
