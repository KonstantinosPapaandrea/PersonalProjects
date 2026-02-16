using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(fileName = "DragonDef", menuName = "TD/Dragon Definition")]
public class DragonDef : ScriptableObject
{
    public string displayName;
    public GameObject prefab;      // Your Dragon prefab (already has Dragon + Attack behaviour)
    public Sprite icon;            // Button icon
    public int cost = 25;
    [TextArea] public string description;
}
