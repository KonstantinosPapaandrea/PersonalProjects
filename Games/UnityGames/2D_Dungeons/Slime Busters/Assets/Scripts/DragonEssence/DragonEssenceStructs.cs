using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public struct MatchStats
{
    public int wavesCleared;
    public bool won;
    public int livesStart, livesEnd;
    public int enemiesSpawned, enemiesLeaked;
    public int bossesKilled;
    public float runSeconds;
    public int difficultyTier; // 0=Normal,1=Hard,2=Brutal...
    public int streakWins;     // load from profile before Award()
}

