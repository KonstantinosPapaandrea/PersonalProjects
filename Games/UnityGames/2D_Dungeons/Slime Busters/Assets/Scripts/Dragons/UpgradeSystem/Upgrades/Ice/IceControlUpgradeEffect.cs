using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Ice/Control Upgrade", fileName = "FX_Ice_Control")]
public class IceControlUpgradeEffect : UpgradeEffectSO
{
    [Header("Base Cone Tweaks (optional)")]
    public bool tweakCone;
    public float coneAngle = 45f;
    public float coneRange = 3.25f;

    [Header("Base Slow Tweaks (optional)")]
    public bool tweakBaseSlow;
    [Range(0f, 1f)] public float baseSlowPct = 0.45f;
    public float baseSlowDur = 2.0f;

    [Header("Freeze On Hit")]
    public bool enableFreeze = true;
    [Range(0f, 1f)] public float freezeChance = 0.15f;
    public float freezeDuration = 1.0f;

    [Header("Frozen Ground (optional)")]
    public bool enableGround = true;
    public GameObject groundPatchPrefab;
    public float groundCooldown = 3.5f;
    public float groundRadius = 1.35f;
    public float groundDuration = 4.0f;

    public override void Apply(Dragon d)
    {
        var ia = d.attack as IceAttack;
        if (!ia)
        {
            Debug.LogWarning("IceControlUpgradeEffect applied to non-Ice dragon.", d);
            return;
        }

        if (tweakCone) ia.SetCone(coneAngle, coneRange);
        if (tweakBaseSlow) ia.SetBaseSlow(baseSlowPct, baseSlowDur);

        if (enableFreeze && freezeDuration > 0f) ia.EnableFreeze(freezeChance, freezeDuration);

        if (enableGround && groundPatchPrefab)
            ia.EnableFrozenGround(groundPatchPrefab, groundCooldown, groundRadius, groundDuration);
    }

    public override void Remove(Dragon d) { }
}
