using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.SceneManagement;
using System.Collections;
using SlimeBusters;

public class YouWinUI : MonoBehaviour
{
    [Header("Wiring")]
    [SerializeField] CanvasGroup panel;
    [SerializeField] TMP_Text titleText;
    [SerializeField] TMP_Text essenceText;
    [SerializeField] Button backToMenuButton;

    [Header("Animation")]
    [SerializeField, Tooltip("Seconds for the panel to fade in")]
    float fadeDuration = 0.35f;

    [SerializeField, Tooltip("Seconds for the essence number to count up")]
    float countDuration = 1.2f;

    [SerializeField] AnimationCurve ease = AnimationCurve.EaseInOut(0, 0, 1, 1);

    [SerializeField, Tooltip("Disable the back button until the counter finishes")]
    bool lockBackButtonDuringCount = true;

    [SerializeField, Tooltip("Show + for positive rewards")]
    bool showPlusSign = true;

    [SerializeField, Tooltip("Add thousands separators, e.g., 12,345")]
    bool thousandsSeparator = true;

    int lastRunEssence;
    Coroutine playCo;

    void Awake()
    {
        GameSignals.OnRunEssenceAwarded += CaptureEssence;
        GameSignals.OnWin += HandleWin;

        HideInstant();
        if (backToMenuButton) backToMenuButton.onClick.AddListener(BackToMenu);
    }

    void OnDestroy()
    {
        GameSignals.OnRunEssenceAwarded -= CaptureEssence;
        GameSignals.OnWin -= HandleWin;
        if (backToMenuButton) backToMenuButton.onClick.RemoveListener(BackToMenu);
    }

    void CaptureEssence(int amount) { lastRunEssence = amount; }

    void HandleWin()
    {
        if (playCo != null) StopCoroutine(playCo);
        playCo = StartCoroutine(ShowWinNextFrame());
    }

    IEnumerator ShowWinNextFrame()
    {
        // Let awarding systems finish this frame
        yield return null;

        // Pause gameplay, but we’ll animate with unscaled time.
        Time.timeScale = 0f;

        // Resolve the final awarded amount robustly
        int amount = lastRunEssence;
        if (amount == 0 && EssenceRunReporter.I != null && EssenceRunReporter.I.RunAward != 0)
            amount = EssenceRunReporter.I.RunAward;
        if (amount == 0 && DragonEssenceManager.Instance != null)
            amount = DragonEssenceManager.Instance.LastAwardDelta;

        if (titleText) titleText.text = "YOU WIN!";

        // Prepare UI
        if (lockBackButtonDuringCount && backToMenuButton) backToMenuButton.interactable = false;
        if (essenceText) essenceText.text = FormatEssence(0);

        // Fade panel in
        yield return StartCoroutine(FadeCanvasGroup(panel, 0f, 1f, fadeDuration));

        // Count 0 -> amount
        yield return StartCoroutine(CountEssence(0, amount, countDuration));

        if (lockBackButtonDuringCount && backToMenuButton) backToMenuButton.interactable = true;
    }

    IEnumerator CountEssence(int from, int to, float duration)
    {
        if (!essenceText || duration <= 0f)
        {
            if (essenceText) essenceText.text = FormatEssence(to);
            yield break;
        }

        float t = 0f;
        while (t < 1f)
        {
            t += Time.unscaledDeltaTime / duration;
            float k = ease != null ? Mathf.Clamp01(ease.Evaluate(Mathf.Clamp01(t))) : Mathf.Clamp01(t);
            int val = Mathf.RoundToInt(Mathf.Lerp(from, to, k));
            essenceText.text = FormatEssence(val);
            yield return null;
        }
        essenceText.text = FormatEssence(to);
    }

    string FormatEssence(int value)
    {
        // Prefix + for positives if desired
        string sign = (value > 0 && showPlusSign) ? "+" : "";
        string num = thousandsSeparator ? value.ToString("N0") : value.ToString();
        return $"Essence:{sign}{num}";
    }

    IEnumerator FadeCanvasGroup(CanvasGroup cg, float from, float to, float duration)
    {
        if (!cg) yield break;
        cg.blocksRaycasts = true; // so clicks don’t pass through during fade
        cg.interactable = false;
        cg.alpha = from;

        float t = 0f;
        while (t < 1f)
        {
            t += Time.unscaledDeltaTime / Mathf.Max(0.0001f, duration);
            cg.alpha = Mathf.Lerp(from, to, t);
            yield return null;
        }
        cg.alpha = to;
        cg.interactable = true;
    }

    void BackToMenu()
    {
        Time.timeScale = 1f;
        SceneManager.LoadScene("MainMenu");
    }

    void HideInstant()
    {
        if (!panel) return;
        panel.alpha = 0f;
        panel.interactable = false;
        panel.blocksRaycasts = false;
    }
}
