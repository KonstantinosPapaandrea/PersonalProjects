using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Fire/Pierce & Damage", fileName = "FX_Fire_Pierce")]
public class FirePierceUpgradeEffect : UpgradeEffectSO
{
    [Header("Damage")]
    [Tooltip("Flat damage added to the dragon's base damage.")]
    public int damageAdd = 0;

    [Tooltip("Multiply dragon damage after flat add. 1.2 = +20%.")]
    public float damageMult = 1f;

    [Header("Pierce")]
    [Tooltip("Ensure at least this many pierces (0 = none).")]
    public int pierceMin = 0;

    public override void Apply(Dragon d)
    {
        // bump base damage
        if (damageAdd != 0 || !Mathf.Approximately(damageMult, 1f))
        {
            d.damage = Mathf.RoundToInt((d.damage + damageAdd) * Mathf.Max(0.01f, damageMult));
        }

        // set pierce on FireAttack
        var fa = d.attack as FireAttack;
        if (!fa) return;

        if (pierceMin > 0) fa.SetPierceAtLeast(pierceMin);
    }

    public override void Remove(Dragon d) { }
}
