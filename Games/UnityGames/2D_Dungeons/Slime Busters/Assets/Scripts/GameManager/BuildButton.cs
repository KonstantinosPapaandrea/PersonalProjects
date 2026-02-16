using UnityEngine;

public class BuildButton : MonoBehaviour
{
    public GameObject towerPrefab;
    public int cost = 25;

    public void OnClickBuild()
    {
        if (BuildManager.I == null || towerPrefab == null) return;
        BuildManager.I.BeginPlacing(towerPrefab, cost);
    }
}
