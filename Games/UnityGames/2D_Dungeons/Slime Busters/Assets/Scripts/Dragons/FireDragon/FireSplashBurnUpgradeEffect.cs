using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Fire/Splash & Burn", fileName = "FX_Fire_SplashBurn")]
public class FireSplashBurnUpgradeEffect : UpgradeEffectSO
{
    [Header("Splash")]
    [Tooltip("Ensure at least this splash radius. 0.5 = small, 1.2 = big.")]
    public float splashRadiusMin = 0f;

    [Header("Burn")]
    [Tooltip("Add this much burn DPS (0 = off).")]
    public float burnDpsAdd = 0f;

    [Tooltip("Ensure at least this burn duration in seconds.")]
    public float burnDurationMin = 0f;

    [Header("Optional")]
    [Tooltip("Switch to explosive mode if not already.")]
    public bool switchToExplosiveMode = true;

    public override void Apply(Dragon d)
    {
        var fa = d.attack as FireAttack;
        if (!fa) { Debug.LogWarning("FireSplashBurnUpgradeEffect: target has no FireAttack.", d); return; }

        if (switchToExplosiveMode) fa.SwitchModeToExplosive();

        if (splashRadiusMin > 0f) fa.SetSplashAtLeast(splashRadiusMin);
        if (burnDpsAdd > 0f) fa.AddBurnDps(burnDpsAdd);
        if (burnDurationMin > 0f) fa.SetBurnDurationAtLeast(burnDurationMin);
    }

    public override void Remove(Dragon d) { }
}
