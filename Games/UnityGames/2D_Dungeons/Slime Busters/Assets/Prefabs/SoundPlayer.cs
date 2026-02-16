using UnityEngine;
using UnityEngine.Audio;
using System.Collections.Generic;

public class SoundPlayer : MonoBehaviour
{
    public static SoundPlayer I { get; private set; }

    [Header("Routing")]
    [SerializeField] AudioMixerGroup sfxOutput;
    [SerializeField] AudioMixerGroup musicOutput;   // NEW

    [Header("Pool")]
    [SerializeField, Min(1)] int initialSources = 8;
    [SerializeField, Min(1)] int maxVoices = 24;

    readonly Queue<AudioSource> idle = new Queue<AudioSource>();
    readonly HashSet<AudioSource> busy = new HashSet<AudioSource>();

    void Awake()
    {
        if (I && I != this) { Destroy(gameObject); return; }
        I = this;
        DontDestroyOnLoad(gameObject);
        Warmup();
    }

    void Warmup()
    {
        for (int i = 0; i < initialSources; i++) idle.Enqueue(CreateSource());
    }

    AudioSource CreateSource()
    {
        var go = new GameObject("SFXSource");
        go.transform.SetParent(transform, false);
        var src = go.AddComponent<AudioSource>();
        src.playOnAwake = false;
        src.outputAudioMixerGroup = sfxOutput;
        src.spatialBlend = 1f; // default 3D (set per call)
        src.rolloffMode = AudioRolloffMode.Logarithmic;
        src.maxDistance = 25f;
        return src;
    }

    AudioSource GetSource()
    {
        // Enforce voice limit
        if (busy.Count >= maxVoices)
        {
            // Try to reclaim an idle one first (unlikely) else drop (hard limit)
            if (idle.Count == 0) return null;
        }

        var src = (idle.Count > 0) ? idle.Dequeue() : CreateSource();
        busy.Add(src);
        return src;
    }

    void Release(AudioSource src)
    {
        if (!src) return;
        src.Stop();
        src.clip = null;
        busy.Remove(src);
        idle.Enqueue(src);
    }

    void Update()
    {
        // recycle finished sources
        if (busy.Count == 0) return;
        // copy to avoid allocs? small sets — fine.
        var done = new List<AudioSource>();
        foreach (var s in busy)
            if (!s.isPlaying) done.Add(s);
        foreach (var s in done) Release(s);
    }

    // --------- Public API ---------

    /// <summary>Play a 3D one-shot at position. Returns true if played.</summary>
    public bool PlayAt(AudioClip clip, Vector3 pos, float volume = 1f,
                       float pitch = 1f, float spatialBlend = 1f,
                       float maxDistance = 25f, AudioMixerGroup route = null)
    {
        if (!clip) return false;
        var src = GetSource();
        if (!src) return false;

        var t = src.transform;
        t.position = pos;

        src.outputAudioMixerGroup = route ? route : sfxOutput;
        src.spatialBlend = Mathf.Clamp01(spatialBlend); // 1 = 3D, 0 = 2D
        src.maxDistance = maxDistance;
        src.pitch = Mathf.Max(0.01f, pitch);
        src.volume = Mathf.Clamp01(volume);
        src.PlayOneShot(clip);
        return true;
    }

    /// <summary>Convenience with pitch randomization.</summary>
    public bool PlayAtJitter(AudioClip clip, Vector3 pos, float volume = 1f,
                             Vector2 pitchRange = default, float spatialBlend = 1f,
                             float maxDistance = 25f, AudioMixerGroup route = null)
    {
        if (pitchRange == default) pitchRange = new Vector2(0.97f, 1.03f);
        float p = Random.Range(pitchRange.x, pitchRange.y);
        return PlayAt(clip, pos, volume, p, spatialBlend, maxDistance, route);
    }

    /// <summary>Play a 2D one-shot (UI/global SFX).</summary>
    public bool Play2D(AudioClip clip, float volume = 1f, float pitch = 1f, AudioMixerGroup route = null)
        => PlayAt(clip, Camera.main ? Camera.main.transform.position : Vector3.zero,
                  volume, pitch, 0f, 0f, route);
}
