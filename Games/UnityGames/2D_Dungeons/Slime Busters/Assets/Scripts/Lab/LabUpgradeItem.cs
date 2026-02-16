using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

public class LabUpgradeItem : MonoBehaviour
{
    [Header("UI")]
    public Image icon;
    public TMP_Text title;
    public TMP_Text subtitle;
    public TMP_Text cost;
    public Button buyButton;
    public GameObject purchasedBadge;

    DragonUpgradeSO data;
    Func<DragonUpgradeSO, bool> canBuy;
    Func<DragonUpgradeSO, bool> isPurchased;
    Action<DragonUpgradeSO, Action, Action<string>> onBuy;

    public void Bind(
        DragonUpgradeSO upg,
        DragonUpgrades target,
        Func<DragonUpgradeSO, bool> canBuyFunc,
        Action<DragonUpgradeSO, Action, Action<string>> onBuyAction,
        Func<DragonUpgradeSO, bool> isPurchasedFunc)
    {
        data = upg;
        canBuy = canBuyFunc;
        onBuy = onBuyAction;
        isPurchased = isPurchasedFunc;

        if (icon) icon.sprite = upg.icon;
        if (title) title.text = upg.displayName;
        if (subtitle) subtitle.text = $"Tier {TierLabel(upg.tier)} • {upg.pathName}";
        if (cost) cost.text = $"🪙 {upg.coinCost}   ✨ {upg.essenceCost}";

        RefreshState();

        buyButton.onClick.RemoveAllListeners();
        buyButton.onClick.AddListener(() =>
        {
            buyButton.interactable = false;
            onBuy?.Invoke(upg, () =>
            {
                RefreshState();
            }, (err) =>
            {
                RefreshState(); // re-enable if failed
            });
        });
    }

    void RefreshState()
    {
        bool purchased = isPurchased != null && isPurchased(data);
        if (purchasedBadge) purchasedBadge.SetActive(purchased);
        if (buyButton) buyButton.gameObject.SetActive(!purchased);
        if (buyButton) buyButton.interactable = canBuy != null && canBuy(data);
    }

    static string TierLabel(UpgradeTier t) =>
        t == UpgradeTier.Tier1 ? "I" : t == UpgradeTier.Tier2 ? "II" : "III";
}
