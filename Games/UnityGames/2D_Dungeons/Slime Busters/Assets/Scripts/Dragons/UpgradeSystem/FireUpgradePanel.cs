using UnityEngine;
using SlimeBusters;

public class FireUpgradePanel : MonoBehaviour
{
    [Header("Data")]
    public UpgradeLibrarySO fireLibrary;

    [Header("Refs")]
    public UpgradeManager upgradeManager;
    public Transform buttonsParent;     // a GridLayoutGroup content
    public GameObject buttonPrefab;     // must have UpgradeUIButton + Button + TMP labels

    Dragon current;

    void OnEnable()
    {
        // If re-opened, rebuild for the current target
        if (upgradeManager && upgradeManager.currentTarget)
            ShowFor(upgradeManager.currentTarget);
    }

    public void ShowFor(Dragon d)
    {
        current = d;
        Build();
    }

    void Build()
    {
        foreach (Transform c in buttonsParent) Destroy(c.gameObject);

        if (!current || current.dragonType != DragonType.Fire) return;
        if (!fireLibrary) return;

        // Simple slime count provider (until you wire SlimeTechManager)
        int SlimeCount(SlimeType t) => 999999; // effectively disables gating for now
        Debug.Log("Test");
        foreach (var upg in fireLibrary.upgrades)
        {
            Debug.Log("Test2");

            var go = Instantiate(buttonPrefab, buttonsParent);
            Debug.Log("Test3");

            var ui = go.GetComponent<UpgradeUIButton>();
            Debug.Log("Test4");

            ui.Bind(current, upg, upgradeManager, SlimeCount);
        }
    }

    public void RefreshAll()
    {
        foreach (Transform c in buttonsParent)
        {
            var ui = c.GetComponent<UpgradeUIButton>();
            if (ui) ui.RefreshState();
        }
    }
}
