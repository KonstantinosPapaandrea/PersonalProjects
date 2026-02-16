using UnityEngine;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class UpgradeTester : MonoBehaviour
{
    public Dragon target;                 // drag a Fire Dragon in the scene
    public DragonUpgradeSO upgrade;       // drag your single upgrade asset here
    public bool applyOnStart = true;      // or use hotkey
    public KeyCode hotkey = KeyCode.U;    // press U to apply in play mode

    void Start()
    {
        if (applyOnStart) TryApply();
    }

    void Update()
    {
        if (Input.GetKeyDown(hotkey)) TryApply();
    }

    void TryApply()
    {
        if (!target || !upgrade) { SLB_Debug.LogWarning("Assign target + upgrade."); return; }

        // Fake infinite coins & slime counts for testing
        int coins = int.MaxValue;
        int SlimeCount(SlimeType t) => 999999;

        if (target.upgrades.CanBuy(upgrade, coins, SlimeCount))
        {
            target.upgrades.Buy(upgrade);
            SLB_Debug.Log($"Applied upgrade: {upgrade.name} to {target.name}");
        }
        else
        {
            SLB_Debug.LogWarning("CanBuy returned false  check dragonType, tier/path rules, or gating.");
        }
    }
}

}
