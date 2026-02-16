using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

public class MetaLabItem : MonoBehaviour
{
    [Header("UI")]
    public TMP_Text title;
    public TMP_Text subtitle;
    public TMP_Text cost;
    public TMP_Text ownedBadge;
    public Button buyButton;

    MetaUpgradeNode data;
    Func<bool> isOwned;
    Func<bool> canBuy;
    Action onBuy;

    public void Bind(MetaUpgradeNode node, Func<bool> isOwnedFunc, Action onBuyAction, Func<bool> canBuyFunc)
    {
        data = node;
        isOwned = isOwnedFunc;
        onBuy = onBuyAction;
        canBuy = canBuyFunc;

        if (title) title.text = $"{node.dragonClass} • {node.statKey}";
        if (subtitle) subtitle.text = $"Path {node.path} • Tier {node.tier} • {node.modType} {node.value:+0.##;-0.##}";
        if (cost) cost.text = $"✨ {node.baseCost}";

        buyButton.onClick.RemoveAllListeners();
        buyButton.onClick.AddListener(() => onBuy?.Invoke());

        Refresh();
    }

    public void Refresh()
    {
        bool owned = isOwned?.Invoke() ?? false;
        if (ownedBadge) ownedBadge.gameObject.SetActive(owned);
        if (buyButton)
        {
            buyButton.gameObject.SetActive(!owned);
            buyButton.interactable = (canBuy?.Invoke() ?? false) && !owned;
        }
    }
}
