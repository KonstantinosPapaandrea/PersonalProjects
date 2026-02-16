using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

public class UpgradeCardMeta : MonoBehaviour
{
    [Header("UI")]
    public TMP_Text title;
    public TMP_Text subtitle;
    public TMP_Text cost;
    public TMP_Text ownedBadge;
    public Button buyButton;
    public TMP_Text lockReason; // optional small text under button

    MetaUpgradeNode data;
    Func<bool> isOwned;
    Func<bool> canBuy;
    Action onBuy;
    Func<string> whyLocked;

    public void Bind(
        MetaUpgradeNode node,
        Func<bool> isOwned,
        Action onBuy,
        Func<bool> canBuy,
        Func<string> whyLocked)
    {
        this.data = node;
        this.isOwned = isOwned;
        this.onBuy = onBuy;
        this.canBuy = canBuy;
        this.whyLocked = whyLocked;

        if (title) title.text = $"{node.dragonClass} • {node.statKey}";
        if (subtitle) subtitle.text = $"Path {node.path} • Tier {node.tier} • {node.modType} {FormatVal(node)}";
        if (cost) cost.text = $"✨ {node.baseCost}";

        buyButton.onClick.RemoveAllListeners();
        buyButton.onClick.AddListener(() => this.onBuy?.Invoke());

        Refresh();
    }

    string FormatVal(MetaUpgradeNode n)
    {
        // nice formatting for +1 / ×0.9 styles
        return n.modType == ModType.Multiplicative
            ? $"{n.value:0.##}x"
            : $"{(n.value >= 0 ? "+" : "")}{n.value:0.##}";
    }

    public void Refresh()
    {
        bool owned = isOwned?.Invoke() ?? false;

        if (ownedBadge) ownedBadge.gameObject.SetActive(owned);
        if (buyButton)
        {
            buyButton.gameObject.SetActive(!owned);
            bool can = canBuy?.Invoke() ?? false;
            buyButton.interactable = can;
            if (lockReason)
                lockReason.text = can ? "" : (whyLocked?.Invoke() ?? "");
        }
    }
}
