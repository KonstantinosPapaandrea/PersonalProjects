using UnityEngine;

[CreateAssetMenu(menuName = "TD/Map/Region", fileName = "RegionData_")]
public class RegionData : ScriptableObject
{
    [Header("Identity")]
    public string id;                 // e.g. "grasslands"
    public string displayName;        // e.g. "Grasslands"
    public string sceneName;          // must match Build Settings

    [Header("Map")]
    [Range(0, 1)] public float anchorX = 0.5f; // relative position on the map image
    [Range(0, 1)] public float anchorY = 0.5f; // (0,0) bottom-left, (1,1) top-right
    public Sprite icon;

    [Header("Progression")]
    public int requiredStars = 0;     // total stars player must have to unlock
    public int recommendedDifficulty = 1; // for display only

    [TextArea] public string summary;
}
