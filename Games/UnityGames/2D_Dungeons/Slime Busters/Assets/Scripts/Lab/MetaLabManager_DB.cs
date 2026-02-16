using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Linq;
using System.Xml.Serialization;

public class MetaLabManager_DB : MonoBehaviour
{
    [Header("UI")]
    public TMP_Text essenceText;
    public Transform gridParent;
    //public MetaLabItem itemPrefab;
    public TMP_Dropdown dragonFilter; // optional

    string currentClass = null;

    void OnEnable() { Invoke(nameof(Initialize), 0.02f); }

    void Initialize()
    {
        if (!gridParent)
        {
            Debug.LogError("[MetaLab] Assign gridParent & itemPrefab.");
            return;
        }

        if (MetaUpgradeDatabase.Instance == null)
        {
            Debug.LogError("[MetaLab] No MetaUpgradeDatabase in Resources/. Create it via Tools→Meta Upgrades.");
            return;
        }

        BuildFilter();

 
    }
  

    void BuildFilter()
    {
        if (!dragonFilter) return;
        dragonFilter.onValueChanged.RemoveAllListeners();
        dragonFilter.ClearOptions();
        dragonFilter.options.Add(new TMP_Dropdown.OptionData("All"));

        var db = MetaUpgradeDatabase.Instance;
        if (db.nodes != null)
        {
            foreach (var cls in db.nodes.Where(n => n)
                                        .Select(n => n.dragonClass)
                                        .Where(s => !string.IsNullOrEmpty(s))
                                        .Distinct())
                dragonFilter.options.Add(new TMP_Dropdown.OptionData(cls));
        }

        dragonFilter.value = 0;
        dragonFilter.RefreshShownValue();
        dragonFilter.onValueChanged.AddListener(i =>
        {
            currentClass = (i == 0) ? null : dragonFilter.options[i].text;
          
        });
    }



    void RefreshWallet()
    {
        int val = DragonEssenceManager.Instance ? DragonEssenceManager.Instance.Balance : 0;
        if (essenceText) essenceText.text = $"Essence: {val}";
    }

    void RefreshLayout()
    {
        Canvas.ForceUpdateCanvases();
        var rt = gridParent as RectTransform;
        if (rt) UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(rt);
    }
    bool IsOwned(string nodeId)
    {
        var mgr = DragonEssenceManager.Instance;
        if (!mgr) return false;
        var list = mgr.UpgradeLevels;
        if (list == null) return false;
        return list.Any(u => u.key == nodeId && u.level > 0);
    }

    bool PrereqOK(MetaUpgradeNode node)
    {
        return node.prerequisite == null || IsOwned(node.prerequisite.id);
    }

    // ✅ node.path is a string ("A","B","C"), so compare strings
    bool PathLockOK(MetaUpgradeNode node)
    {
        if (node.tier <= 1) return true;

        var db = MetaUpgradeDatabase.Instance;
        var ownedTier2PlusSameClass = db.nodes.Where(n => n && n.dragonClass == node.dragonClass && n.tier >= 2 && IsOwned(n.id));
        if (!ownedTier2PlusSameClass.Any()) return true;

        string chosenPath = ownedTier2PlusSameClass.First().path;  // ✅ string  :contentReference[oaicite:5]{index=5}
        return node.path == chosenPath;                             // ✅ string compare
    }

    bool CanBuy(MetaUpgradeNode node, out string why)
    {
        if (IsOwned(node.id)) { why = "Already owned."; return false; }
        if (!PrereqOK(node)) { why = "Missing prerequisite."; return false; }
        if (!PathLockOK(node)) { why = "Locked to another path."; return false; }
        if (DragonEssenceManager.Instance.Balance < node.baseCost) { why = "Not enough essence."; return false; }
        why = null; return true;
    }



    void ResizeContentToGrid()
{
    var contentRT = (RectTransform)gridParent;
    var grid = contentRT.GetComponent<GridLayoutGroup>();
    if (!grid) return;

    // how many visible children?
    int count = 0;
    for (int i = 0; i < contentRT.childCount; i++)
        if (contentRT.GetChild(i).gameObject.activeInHierarchy) count++;

    // columns from the constraint
    int cols = (grid.constraint == GridLayoutGroup.Constraint.FixedColumnCount && grid.constraintCount > 0)
        ? grid.constraintCount
        : Mathf.Max(1, Mathf.FloorToInt(((RectTransform)grid.transform.parent).rect.width / (grid.cellSize.x + grid.spacing.x)));

    int rows = Mathf.CeilToInt((float)count / cols);

    // compute required size from grid settings
    float w = grid.padding.left
            + cols * grid.cellSize.x
            + (cols - 1) * grid.spacing.x
            + grid.padding.right;

    float h = grid.padding.top
            + rows * grid.cellSize.y
            + (rows - 1) * grid.spacing.y
            + grid.padding.bottom;

    // IMPORTANT: Content should be top-anchored; sizeDelta drives its size.
    contentRT.sizeDelta = new Vector2(w, h);

    // force layout to update now
    Canvas.ForceUpdateCanvases();
    LayoutRebuilder.ForceRebuildLayoutImmediate(contentRT);
}

}
