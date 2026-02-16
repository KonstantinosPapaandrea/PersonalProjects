using UnityEngine;

public enum ModType { Additive, Multiplicative, Toggle }

[CreateAssetMenu(menuName = "DB/MetaUpgradeNode")]
public class MetaUpgradeNode : ScriptableObject
{
    public string id;            // e.g., "Lightning.A.1"
    public string dragonClass;   // "Lightning","Fire","EggPlanter","Crystal","Ice"
    public string path;          // "A" | "B" | "C"
    public int tier;             // 1..5
    public int baseCost;         // essence cost
    public ModType modType;
    public string statKey;       // e.g., "ChainRange","AuraDPS","EggHatchSpeed"
    public float value;          // magnitude at this tier
    public MetaUpgradeNode prerequisite; // optional
}
