using UnityEngine;

public class EnemyCounter : MonoBehaviour
{
    public static EnemyCounter I { get; private set; }
    public int Spawned { get; private set; }
    public int Leaked { get; private set; }

    void Awake() { if (I == null) I = this; else Destroy(gameObject); }

    public static void OnSpawn() { if (I) I.Spawned++; }
    public static void OnLeak() { if (I) I.Leaked++; }
}
