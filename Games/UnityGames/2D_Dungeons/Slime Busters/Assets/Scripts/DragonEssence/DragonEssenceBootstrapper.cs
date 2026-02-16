// DragonEssenceBootstrapper.cs
using UnityEngine;
public static class DragonEssenceBootstrapper
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    static void EnsureEssenceManager()
    {
        if (DragonEssenceManager.Instance != null) return;

        var prefab = Resources.Load<GameObject>("Prefabs/DragonEssence");
        if (prefab != null)
        {
            Object.Instantiate(prefab);
            Debug.Log("[EssenceBoot] Spawned DragonEssence prefab");
            return;
        }
        var go = new GameObject("DragonEssence (Auto)");
        go.AddComponent<DragonEssenceManager>();
        Debug.Log("[EssenceBoot] Created DragonEssence manager");
    }
}
