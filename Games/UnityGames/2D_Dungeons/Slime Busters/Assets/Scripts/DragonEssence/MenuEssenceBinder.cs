// MenuEssenceBinder.cs
using UnityEngine;
using TMPro; // or using UnityEngine.UI for non-TMP

public class MenuEssenceBinder : MonoBehaviour
{
    [SerializeField] TMP_Text label; // assign in Inspector

    void Awake()
    {
        if (!label) label = GetComponent<TMP_Text>();
        UpdateLabel();
        // live updates when you return to menu after a run
        if (DragonEssenceManager.Instance != null)
            DragonEssenceManager.Instance.OnEssenceAwarded += OnAwarded;
    }

    void OnDestroy()
    {
        if (DragonEssenceManager.Instance != null)
            DragonEssenceManager.Instance.OnEssenceAwarded -= OnAwarded;
    }

    void OnEnable() { UpdateLabel(); } // also refresh when the menu opens

    void OnAwarded(int _) { UpdateLabel(); }

    void UpdateLabel()
    {
        var mgr = DragonEssenceManager.Instance;
        if (!mgr) { if (label) label.text = "Essence: —"; return; }
        if (label) label.text = $"Essence: {mgr.Balance}";
    }
}
