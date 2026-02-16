using System.Collections.Generic;
using UnityEngine;

[CreateAssetMenu(menuName = "TD/Upgrades/Upgrade Library", fileName = "UpgradeLibrary")]
public class UpgradeLibrarySO : ScriptableObject
{
    public DragonType dragonType;
    public List<DragonUpgradeSO> upgrades; // put them in display order (T1s then T2s then T3s)
}
