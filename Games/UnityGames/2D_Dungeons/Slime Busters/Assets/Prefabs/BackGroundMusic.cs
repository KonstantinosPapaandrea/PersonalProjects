using UnityEngine;

[RequireComponent(typeof(AudioSource))]
public class BackgroundMusic : MonoBehaviour
{
    [Header("Clip")]
    [SerializeField] AudioClip music;        // drop your track here

    [Header("Options")]
    [SerializeField] bool playOnStart = true;
    [SerializeField] bool loop = true;
    [SerializeField, Range(0f, 1f)] float volume = 1f;
    [SerializeField] bool stayAcrossScenes = true; // DontDestroyOnLoad

    AudioSource src;

    void Awake()
    {
        src = GetComponent<AudioSource>();
        if (stayAcrossScenes) DontDestroyOnLoad(gameObject);

        src.clip = music;
        src.loop = loop;
        src.spatialBlend = 0f;          // 2D
        src.playOnAwake = false;        // we control start
        src.volume = volume;
        src.outputAudioMixerGroup = null; // assign a Music mixer group if you have one

        if (playOnStart && music) src.Play();
    }

    // tiny helpers if you want to control it from other scripts/UI
    public void Play() { if (music) { src.clip = music; src.loop = loop; src.volume = volume; src.Play(); } }
    public void Stop() { src.Stop(); }
    public void Pause() { src.Pause(); }
    public void SetVolume(float v01) { volume = Mathf.Clamp01(v01); src.volume = volume; }
}
