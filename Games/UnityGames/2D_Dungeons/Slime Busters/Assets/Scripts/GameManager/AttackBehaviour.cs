namespace SlimeBusters
{
﻿using UnityEngine;

public abstract class AttackBehaviour : MonoBehaviour
{
    [SerializeField] protected GameObject bulletPrefab;  // ← keep only here
    public virtual bool RequiresTarget => true;
    public virtual void Bind(Dragon d) { owner = d; }
    protected Dragon owner;
    public virtual void Tick(float dt) { }
    public virtual bool CanFireNow() => true;
    public abstract void Fire(Vector3 origin, Enemy target, Dragon owner);
}

}
