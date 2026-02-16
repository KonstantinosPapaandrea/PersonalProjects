using System.Collections.Generic;
using UnityEngine;
using SlimeBusters.Internal;

namespace SlimeBusters
{

public class DragonUpgradePanel : MonoBehaviour
{
    [System.Serializable] public class LibraryMap { public DragonType type; public UpgradeLibrarySO library; }

    public List<LibraryMap> libraries = new();
    public UpgradeManager upgradeManager;
    public Transform buttonsParent;
    public GameObject buttonPrefab;

    Dictionary<DragonType, UpgradeLibrarySO> _map;
    Dragon _current;

    void Awake()
    {
        _map = new Dictionary<DragonType, UpgradeLibrarySO>();
        foreach (var m in libraries)
        {
            if (m == null || m.library == null) continue;
            _map[m.type] = m.library;
        }
    }

    void OnEnable()
    {
        // If panel is re-opened quickly, rebuild for current target
        if (upgradeManager && upgradeManager.currentTarget) ShowFor(upgradeManager.currentTarget);
    }

    public void ShowFor(Dragon d)
    {
        _current = d;
        Build();
    }

    void Build()
    {
        // Clear existing buttons
        if (buttonsParent)
            foreach (Transform c in buttonsParent) Destroy(c.gameObject);

        if (_current == null)
        {
            SLB_Debug.LogWarning("[DragonUpgradePanel] No current target; hiding panel.");
            gameObject.SetActive(false);
            return;
        }

        // Find the upgrade library for the current dragon type
        if (!_map.TryGetValue(_current.dragonType, out var lib) || lib == null)
        {
            SLB_Debug.LogError($"[DragonUpgradePanel] No library assigned for {_current.dragonType}. " +
                           $"Configured types: {string.Join(", ", _map.Keys)}");
            gameObject.SetActive(false);
            return;
        }

        if (lib.upgrades == null || lib.upgrades.Count == 0)
        {
            SLB_Debug.LogWarning($"[DragonUpgradePanel] Library '{lib.name}' has 0 upgrades.");
            gameObject.SetActive(true); // Show empty state if you want
            return;
        }

        if (!buttonPrefab)
        {
            SLB_Debug.LogError("[DragonUpgradePanel] buttonPrefab not assigned.");
            return;
        }
        if (!buttonsParent)
        {
            SLB_Debug.LogError("[DragonUpgradePanel] buttonsParent not assigned.");
            return;
        }

        // Debugging: Log the number of upgrades
        SLB_Debug.Log($"[DragonUpgradePanel] Library '{lib.name}' contains {lib.upgrades.Count} upgrades.");

        // Instantiate buttons for each upgrade
        foreach (var upg in lib.upgrades)
        {
            SLB_Debug.Log($"[DragonUpgradePanel] Creating button for upgrade: {upg.displayName}");

            var go = Instantiate(buttonPrefab, buttonsParent);
            var ui = SLB_ComponentCache.Get<UpgradeUIButton>(go);
            if (!ui)
            {
                SLB_Debug.LogError("[DragonUpgradePanel] buttonPrefab missing UpgradeUIButton.", go);
                continue;
            }
            // Bind the upgrade data to the button
            ui.Bind(_current, upg, upgradeManager, (SlimeType t) => 0); // Placeholder for slime count logic
        }

        gameObject.SetActive(true);
        SLB_Debug.Log($"[DragonUpgradePanel] Built {_current.dragonType} panel with {lib.upgrades.Count} upgrades.");
    }

    // Refresh all buttons when necessary
    public void RefreshAll()
    {
        if (!buttonsParent) return;
        foreach (Transform c in buttonsParent)
        {
            var ui = SLB_ComponentCache.Get<UpgradeUIButton>(c);
            if (ui) ui.RefreshState();
        }
    }

}

}
