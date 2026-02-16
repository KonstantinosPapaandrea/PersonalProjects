using UnityEngine;
using UnityEngine.UI;
using TMPro;
using SlimeBusters;

public class UpgradeUIButton : MonoBehaviour
{
    [Header("UI")]
    public Button button;
    public TMP_Text label;
    public TMP_Text costLabel;
    public GameObject lockedOverlay;     // Optional dim/lock icon object

    [Header("Data")]
    public DragonUpgradeSO upgrade;      // Assign at runtime
    public UpgradeManager upgradeManager; // Set at runtime
    public System.Func<SlimeType, int> slimeCount; // Set at runtime

    Dragon target;

    public void Bind(Dragon targetDragon, DragonUpgradeSO upg, UpgradeManager mgr, System.Func<SlimeType, int> slimeCounter)
    {
        target = targetDragon;
        upgrade = upg;
        upgradeManager = mgr;
        slimeCount = slimeCounter;

        if (label) label.text = string.IsNullOrEmpty(upgrade.displayName) ? upgrade.name : upgrade.displayName;

        // If the upgrade is unlocked via essence or coins
        if (IsUpgradeUnlocked())
        {
            // If unlocked, show only the coin cost
            if (costLabel)
            {
                costLabel.text = $"Coins: {upgrade.coinCost}";
            }

            // Ensure the listener is set for coin purchase
            button.onClick.RemoveAllListeners();
            button.onClick.AddListener(OnClickForCoins); // For coin purchase
        }
        else
        {
            // If locked by essence, show essence cost and allow unlocking
            if (costLabel)
            {
                costLabel.text = $"Essence: {upgrade.essenceCost}";
            }

            // Ensure the listener is set for essence unlock
            button.onClick.RemoveAllListeners();
            button.onClick.AddListener(OnClickForEssenceUnlock); // For essence unlock
        }

        RefreshState(); // Initial state
    }

    public void RefreshState()
    {
        if (button == null)
        {
            Debug.LogError("[UpgradeUIButton] Button reference not assigned on prefab.", this);
            return;
        }

        if (target == null || upgrade == null)
        {
            button.interactable = false;
            if (lockedOverlay) lockedOverlay.SetActive(true);
            return;
        }

        // If GameManager not ready, assume infinite coins during panel build to avoid NRE
        int coins = (GameManager.Instance != null) ? GameManager.Instance.coins : int.MaxValue;
        int SlimeCount(SlimeType t) => slimeCount != null ? slimeCount(t) : 0;

        // If the upgrade is unlocked (by essence or coins), check for coins to buy
        if (IsUpgradeUnlocked())
        {
            bool canBuy = target.upgrades != null && target.upgrades.CanBuy(upgrade, coins, SlimeCount);
            button.interactable = canBuy;
            if (lockedOverlay) lockedOverlay.SetActive(!canBuy); // Only lock if can't afford coins
        }
        else
        {
            // If the upgrade is locked by essence, allow unlocking if enough essence
            bool canUnlock = DragonEssenceManager.Instance.Balance >= upgrade.essenceCost;
            button.interactable = canUnlock;
            if (lockedOverlay) lockedOverlay.SetActive(!canUnlock); // Show locked overlay if no essence
        }
    }

    void OnClickForEssenceUnlock()
    {
        if (target == null || upgrade == null) return;

        // Attempt to unlock the upgrade with essence, without actually buying it for the current run
        if (DragonEssenceManager.Instance.Balance >= upgrade.essenceCost)
        {
            // Unlock the upgrade permanently with essence
            DragonEssenceManager.Instance.TryPurchase(upgrade.upgradeId, upgrade.essenceCost); // Deduct essence
            Debug.Log($"[UpgradeUIButton] {upgrade.displayName} unlocked permanently!");

            // After unlocking with essence, update the cost label to coin cost and refresh the button state
            costLabel.text = $"Coins: {upgrade.coinCost}";  // Update the cost label to show coin cost
            button.onClick.RemoveAllListeners();  // Remove old listener
            button.onClick.AddListener(OnClickForCoins); // Add the new listener for coin purchase
            RefreshState();  // Refresh the current button state
            GetComponentInParent<DragonUpgradePanel>()?.RefreshAll();  // Refresh the entire panel if needed
        }
        else
        {
            Debug.Log("Not enough essence to unlock this upgrade.");
        }
    }

    void OnClickForCoins()
    {
        if (target == null || upgrade == null) return;

        int coins = GameManager.Instance.coins;
        int SC(SlimeType t) => (slimeCount != null) ? slimeCount(t) : 0;

        // Check if the player can buy the upgrade with coins
        if (target.upgrades.CanBuy(upgrade, coins, SC))
        {
            GameManager.Instance.SpendCoins(upgrade.coinCost);
            target.upgrades.Buy(upgrade); // Mark the upgrade as purchased

            // Ask manager to refresh panel labels etc.
            upgradeManager.Refresh(target);

            // After purchase, all buttons should update (path lock might have changed)
            GetComponentInParent<FireUpgradePanel>()?.RefreshAll();
        }
        else
        {
            Debug.Log("Not enough coins to purchase this upgrade.");
        }
    }

    // Helper method to check if the upgrade is unlocked (either by essence or coins)
    bool IsUpgradeUnlocked()
    {
        // Check if the upgrade exists in the saved upgrades list (unlocked via essence or coins)
        bool unlockedByEssence = DragonEssenceManager.Instance.UpgradeLevels.Exists(u => u.key == upgrade.upgradeId);
        bool unlockedByCoins = target.upgrades.purchased.Contains(upgrade);


        return unlockedByEssence || unlockedByCoins;
    }

    void SetLocked(bool on, string reason = "")
    {
        button.interactable = !on;
        if (lockedOverlay) lockedOverlay.SetActive(on);
    }
}
