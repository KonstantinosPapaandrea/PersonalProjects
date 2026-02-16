#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using System.Collections.Generic;
using System.Linq;
using SlimeBusters;

public static class MetaDBBuilder
{
    const string RES_DIR = "Assets/Resources";
    const string DB_PATH = RES_DIR + "/MetaUpgradeDatabase.asset";
    const string NODES_DIR = "Assets/MetaUpgradeNodes";

    [MenuItem("Tools/Meta Upgrades/Build from Save (seed nodes)")]
    static void BuildFromSave()
    {
        EnsureFolders();

        // Load or create DB
        var db = AssetDatabase.LoadAssetAtPath<MetaUpgradeDatabase>(DB_PATH);
        if (!db)
        {
            db = ScriptableObject.CreateInstance<MetaUpgradeDatabase>();
            AssetDatabase.CreateAsset(db, DB_PATH);
            Debug.Log("[MetaDB] Created DB.");
        }

        var sceneMgr = Object.FindObjectOfType<DragonEssenceManager>();
        if (!sceneMgr) { Debug.LogError("[MetaDB] Run a scene with DragonEssenceManager in it."); return; }

        var keys = new HashSet<string>(sceneMgr.UpgradeLevels.Select(u => u.key).Where(k => !string.IsNullOrEmpty(k)));
        int created = 0;

        foreach (var key in keys)
        {
            // ✅ GetNode is static
            if (MetaUpgradeDatabase.GetNode(key) != null) continue;  // :contentReference[oaicite:2]{index=2}

            // Try to parse "111" → d=1, p=1, t=1
            int d = 0, p = 0, t = 1;
            if (key.Length >= 3
                && int.TryParse(key.Substring(0, 1), out d)
                && int.TryParse(key.Substring(1, 1), out p)
                && int.TryParse(key.Substring(2, 1), out t)) { }

            // Map numeric path → "A"/"B"/"C" (fallback to number-as-string)
            string PathLabel(int pi) => pi == 1 ? "A" : pi == 2 ? "B" : pi == 3 ? "C" : pi.ToString();

            var node = ScriptableObject.CreateInstance<MetaUpgradeNode>();
            node.id = key;
            node.dragonClass = $"Dragon{d}";
            node.path = PathLabel(p);                    // ✅ string, not int  :contentReference[oaicite:3]{index=3}
            node.tier = t;
            node.baseCost = 20;
            node.modType = ModType.Additive;            // ✅ enum, not string  :contentReference[oaicite:4]{index=4}
            node.statKey = "damage";
            node.value = 1f;

            string assetPath = $"{NODES_DIR}/node_{key}.asset";
            AssetDatabase.CreateAsset(node, assetPath);
            db.nodes.Add(node);
            created++;
        }

        EditorUtility.SetDirty(db);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log($"[MetaDB] Seeded {created} nodes from save. DB now has {db.nodes.Count} nodes at {DB_PATH}.");
    }

    static void EnsureFolders()
    {
        if (!AssetDatabase.IsValidFolder("Assets/Resources"))
            AssetDatabase.CreateFolder("Assets", "Resources");
        if (!AssetDatabase.IsValidFolder("Assets/MetaUpgradeNodes"))
            AssetDatabase.CreateFolder("Assets", "MetaUpgradeNodes");
    }
}
#endif
