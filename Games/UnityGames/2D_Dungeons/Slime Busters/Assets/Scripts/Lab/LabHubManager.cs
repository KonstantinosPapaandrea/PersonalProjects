using System;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class LabHubManager : MonoBehaviour
{
    [Serializable]
    public class JarHotspot
    {
        [Tooltip("Must match MetaUpgradeDatabase node.dragonClass (e.g. Fire, Ice, Nature, etc.)")]
        public string dragonClass;

        [Tooltip("Invisible UI Button placed over the jar area")]
        public Button button;
    }

    [Header("Jar hotspots (click the jars)")]
    [Tooltip("Assign one element per jar. Drag the invisible Button over each jar and set its dragonClass.")]
    public JarHotspot[] jarHotspots;

    [Header("Essence")]
    public TMP_Text essenceText;

    [Header("Upgrades panel")]
    public GameObject upgradesPanel;        // Whole panel (enable/disable)
    public TMP_Text upgradesHeader;         // "Fire Upgrades" etc (optional)
    public Transform upgradesGridContent;   // ScrollView/Viewport/Content
    public UpgradeCardMeta upgradeCardPrefab;

    string currentDragonClass; // e.g., "Fire", "Ice"

    void Start()
    {
        if (!MetaUpgradeDatabase.Instance || MetaUpgradeDatabase.Instance.nodes == null)
        {
            Debug.LogError("[LabHub] DB missing or empty. Put MetaUpgradeDatabase.asset in Resources.");
            return;
        }

        WireJarHotspots();   // clicks on jars open upgrades for that class
        RefreshEssence();
        CloseUpgrades();     // start hidden
    }

    void WireJarHotspots()
    {
        if (jarHotspots == null) return;

        foreach (var h in jarHotspots)
        {
            if (h == null || h.button == null || string.IsNullOrEmpty(h.dragonClass)) continue;

            string cls = h.dragonClass; // capture for closure
            h.button.onClick.RemoveAllListeners();
            h.button.onClick.AddListener(() => OpenUpgrades(cls));
        }
    }

    void RefreshEssence()
    {
        if (essenceText)
            essenceText.text = $"Essence: {(DragonEssenceManager.Instance ? DragonEssenceManager.Instance.Balance : 0)}";
    }

    // === Upgrades panel ===

    public void OpenUpgrades(string dragonClass)
    {
        currentDragonClass = dragonClass;

        if (upgradesHeader)
            upgradesHeader.text = $"{dragonClass} Upgrades";

        upgradesPanel.SetActive(true);
        RebuildUpgrades();
    }

    public void CloseUpgrades()
    {
        upgradesPanel.SetActive(false);
    }

    void RebuildUpgrades()
    {
        foreach (Transform c in upgradesGridContent) Destroy(c.gameObject);

        var nodes = MetaUpgradeDatabase.Instance.nodes
            .Where(n => n && n.dragonClass == currentDragonClass)
            .OrderBy(n => n.tier).ThenBy(n => n.path);

        foreach (var node in nodes)
        {
            var card = Instantiate(upgradeCardPrefab, upgradesGridContent);
            card.Bind(node,
                isOwned: () => IsOwned(node.id),
                onBuy: () =>
                {
                    bool ok = DragonEssenceManager.Instance.TryPurchase(node.id, node.baseCost);
                    if (!ok) Debug.LogWarning($"[LabHub] Purchase failed: {node.id}");
                    RefreshEssence();
                    card.Refresh();
                },
                canBuy: () => CanBuy(node, out _),
                whyLocked: () => { CanBuy(node, out var why); return why; }
            );
        }

        // nudge layout
        Canvas.ForceUpdateCanvases();
        var rt = upgradesGridContent as RectTransform;
        if (rt) UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(rt);
    }

    bool IsOwned(string nodeId)
    {
        var list = DragonEssenceManager.Instance?.UpgradeLevels;
        return list != null && list.Any(u => u.key == nodeId && u.level > 0);
    }

    bool PrereqOK(MetaUpgradeNode n)
        => n.prerequisite == null || IsOwned(n.prerequisite.id);

    bool PathLockOK(MetaUpgradeNode n)
    {
        if (n.tier <= 1) return true;

        var owned = MetaUpgradeDatabase.Instance.nodes
            .Where(x => x && x.dragonClass == n.dragonClass && x.tier >= 2 && IsOwned(x.id));

        if (!owned.Any()) return true;

        var chosenPath = owned.First().path; // string like "A"
        return n.path == chosenPath;
    }

    bool CanBuy(MetaUpgradeNode n, out string why)
    {
        if (IsOwned(n.id)) { why = "Already owned"; return false; }
        if (!PrereqOK(n)) { why = "Missing prerequisite"; return false; }
        //if (!PathLockOK(n)) { why = "Locked to another path"; return false; }
        if (DragonEssenceManager.Instance.Balance < n.baseCost) { why = "Not enough essence"; return false; }
        why = null; return true;
    }
}
