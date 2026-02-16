using UnityEngine;

public class BossTracker : MonoBehaviour
{
    public int Killed { get; private set; }
    public void OnBossKilled() { Killed++; }
}
