using UnityEngine;
using TMPro; // optional, if you show the label

public class GameSpeedController : MonoBehaviour
{
    [Header("Speeds (game-time)")]
    public float[] speeds = { 1f, 2f, 3f };
    public int startIndex = 0;

    [Header("Optional UI")]
    public TMP_Text speedLabel;   // drag a TextMeshPro label if you want to show "x2"

    float baseFixedDeltaTime;     // store the engine default (usually 0.02)

    int _idx;

    void Awake()
    {
        baseFixedDeltaTime = Time.fixedDeltaTime;
        _idx = Mathf.Clamp(startIndex, 0, speeds.Length - 1);
        ApplySpeed(speeds[_idx]);
    }

    public void CycleSpeed()
    {
        _idx = (_idx + 1) % speeds.Length;
        ApplySpeed(speeds[_idx]);
    }

    public void SetSpeed(float scale)
    {
        // find closest preset index (optional)
        int closest = 0; float best = float.MaxValue;
        for (int i = 0; i < speeds.Length; i++)
        {
            float d = Mathf.Abs(speeds[i] - scale);
            if (d < best) { best = d; closest = i; }
        }
        _idx = closest;
        ApplySpeed(scale);
    }

    void ApplySpeed(float scale)
    {
        // Main time dilation
        Time.timeScale = Mathf.Max(0f, scale);

        // Keep physics stable relative to visual time
        // (so physics step size matches the sped-up time)
        Time.fixedDeltaTime = baseFixedDeltaTime * Time.timeScale;

        // Optional UI
        if (speedLabel) speedLabel.text = $"x{scale:0.#}";
    }

    // Optional: quick key to toggle in editor
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.F)) CycleSpeed();   // F to cycle speed
        if (Input.GetKeyDown(KeyCode.Space)) PauseToggle();
    }

    public void PauseToggle()
    {
        if (Time.timeScale <= 0f) ApplySpeed(speeds[_idx]);
        else ApplySpeed(0f);
    }
}
