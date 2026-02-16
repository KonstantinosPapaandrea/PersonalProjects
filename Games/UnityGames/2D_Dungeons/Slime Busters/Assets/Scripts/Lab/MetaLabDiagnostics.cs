using UnityEngine;

public class MetaLabDiagnostics : MonoBehaviour
{
    public MetaLabManager_DB lab;

    void Start()
    {
        if (!lab) lab = GetComponent<MetaLabManager_DB>();

        Debug.Log($"[Diag] EssenceText set? {lab.essenceText != null}");
        Debug.Log($"[Diag] GridParent set? {lab.gridParent != null}");
        Debug.Log($"[Diag] DB instance? {MetaUpgradeDatabase.Instance != null}");
        Debug.Log($"[Diag] DB node count: {(MetaUpgradeDatabase.Instance?.nodes?.Count ?? -1)}");
    }
}
