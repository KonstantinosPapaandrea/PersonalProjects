using System.Collections.Generic;
using System.Linq;
using UnityEngine;

[CreateAssetMenu(menuName = "DB/MetaUpgradeDatabase")]
public class MetaUpgradeDatabase : ScriptableObject
{
    public List<MetaUpgradeNode> nodes = new();

    static MetaUpgradeDatabase _instance;
    public static MetaUpgradeDatabase Instance
    {
        get
        {
            if (_instance == null) _instance = Resources.Load<MetaUpgradeDatabase>("MetaUpgradeDatabase");
            return _instance;
        }
    }

    public static IEnumerable<MetaUpgradeNode> ActiveNodesFor(string dragonClass)
    {
        if (Instance == null) yield break;
        var save = DragonEssenceManager.Instance?.UpgradeLevels;
        if (save == null) yield break;

        foreach (var node in Instance.nodes)
        {
            if (node.dragonClass != dragonClass) continue;

            // Check if the upgrade level exists in the list
            var existingUpgrade = save.Find(u => u.key == node.id);
            if (existingUpgrade != null && existingUpgrade.level > 0)
            {
                // this ScriptableObject represents one tier; if you create one asset per tier,
                // "level > 0" means this tier is owned
                yield return node;
            }
        }
    }



    public static MetaUpgradeNode GetNode(string id)
    {
        return Instance?.nodes.FirstOrDefault(n => n.id == id);
    }
}
