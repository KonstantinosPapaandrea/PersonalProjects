using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;
using System.Collections.Generic;

/// <summary>
/// Thin orchestrator for The Lab. No changes to existing systems.
/// Provide wallet/slime delegates from your game to keep it decoupled.
/// </summary>
public class TheLabManager : MonoBehaviour
{
    [Header("Data Sources")]
    [Tooltip("All upgrade assets available in the game (can be filtered by dragon type).")]
    public List<DragonUpgradeSO> allUpgrades = new();

    [Tooltip("Current dragon instance the player is upgrading (the one with DragonUpgrades).")]
    public DragonUpgrades targetUpgrades;   // drag the component from the active dragon object

    [Header("UI")]
    public TMP_Text essenceText;
    public TMP_Text coinsText;
    public Transform gridParent;            // where LabUpgradeItem prefabs go
    public LabUpgradeItem itemPrefab;       // simple prefab with labels + Buy button
    public TMP_Dropdown dragonFilter;       // optional: filter by DragonType
    public Button backButton;

    // --- Injected callbacks to keep backward-compatibility ---
    public Func<int> GetCoins;              // e.g., () => PlayerState.Coins
    public Action<int> SpendCoins;          // e.g., amt => PlayerState.SpendCoins(amt)
    public Func<int> GetEssence;            // e.g., () => DragonEssenceManager.Instance.Balance
    public Action<int> SpendEssence;        // e.g., amt => DragonEssenceManager.Instance.Spend(amt)
    public Func<SlimeType, int> SlimeCount; // e.g., type => Progress.Killed(type)

    // Optional filter state
    DragonType? currentFilter = null;

    void Start()
    {
        // Safe fallbacks if you forget to wire them (won’t break other scenes):
        GetCoins ??= () => 0;
        SpendCoins ??= _ => { };
        GetEssence ??= () => 0;
        SpendEssence ??= _ => { };
        SlimeCount ??= _ => 0;
        backButton.onClick.AddListener(OnBack);

        BuildDragonTypeFilter();
        RefreshWalletUI();
        RebuildGrid();
    }

    void BuildDragonTypeFilter()
    {
        if (!dragonFilter) return;
        var options = new List<TMP_Dropdown.OptionData> { new("All") };
        foreach (DragonType dt in System.Enum.GetValues(typeof(DragonType)))
            options.Add(new TMP_Dropdown.OptionData(dt.ToString()));

        dragonFilter.ClearOptions();
        dragonFilter.AddOptions(options);
        dragonFilter.onValueChanged.AddListener(idx =>
        {
            currentFilter = (idx == 0) ? (DragonType?)null : (DragonType)(idx - 1);
            RebuildGrid();
        });
    }

    void RefreshWalletUI()
    {
        if (essenceText) essenceText.text = $"Essence: {GetEssence()}";
        if (coinsText) coinsText.text = $"Coins: {GetCoins()}";
    }

    void RebuildGrid()
    {
        foreach (Transform c in gridParent) Destroy(c.gameObject);

        foreach (var upg in allUpgrades)
        {
            if (!upg) continue;
            if (currentFilter.HasValue && upg.dragonType != currentFilter.Value) continue;

            var item = Instantiate(itemPrefab, gridParent);
            item.Bind(upg, targetUpgrades, CanBuyAdapter, OnBuyRequested, IsPurchasedAdapter);
        }
    }

    // Wrap your existing CanBuy to inject coins/slimes without changing your class
    bool CanBuyAdapter(DragonUpgradeSO upg)
    {
        return targetUpgrades && targetUpgrades.CanBuy(upg, GetCoins(), SlimeCount);
    }

    bool IsPurchasedAdapter(DragonUpgradeSO upg)
    {
        return targetUpgrades && targetUpgrades.purchased.Contains(upg);
    }

    void OnBuyRequested(DragonUpgradeSO upg, Action onSuccess, Action<string> onFail)
    {
        if (!targetUpgrades)
        {
            onFail?.Invoke("No target dragon bound.");
            return;
        }

        // Respect your CanBuy gate (coins, essence, slimes, prereqs, path rules)
        if (!CanBuyAdapter(upg))
        {
            onFail?.Invoke("Requirements not met.");
            return;
        }

        // Deduct currencies BEFORE calling Buy (your Buy() assumes they were paid)
        // Only charge if not already “unlocked” per your logic; your CanBuy already checks that.
        // Keep it simple: pay both coin & essence costs here.
        int coins = GetCoins();
        if (coins < upg.coinCost) { onFail?.Invoke("Not enough coins."); return; }
        int essence = GetEssence();
        if (essence < upg.essenceCost) { onFail?.Invoke("Not enough essence."); return; }

        SpendCoins(upg.coinCost);
        SpendEssence(upg.essenceCost);
        RefreshWalletUI();

        // Now perform the purchase (applies effects, commits path tier2, saves)
        bool ok = targetUpgrades.Buy(upg);
        if (!ok)
        {
            // refund if something went wrong (paranoid safety)
            SpendCoins(-upg.coinCost);
            SpendEssence(-upg.essenceCost);
            RefreshWalletUI();
            onFail?.Invoke("Purchase failed.");
            return;
        }

        onSuccess?.Invoke();
    }

    void OnBack()
    {
        // Hook your scene loader or menu navigation here.
        // e.g., SceneManager.LoadScene("GameScene");
    }
}
