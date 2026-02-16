using UnityEngine;
using TMPro;

public class EndOfRunPopup : MonoBehaviour
{
    [SerializeField] TMP_Text title;
    [SerializeField] TMP_Text amountLine;
    [SerializeField] TMP_Text detailLine;

    public static void Spawn(EndOfRunPopup prefab, int gained, MatchStats s)
    {
        var canvas = FindObjectOfType<Canvas>();
        var pop = Instantiate(prefab, canvas ? canvas.transform : null);
        pop.Bind(gained, s);
    }

    public void Bind(int gained, MatchStats s)
    {
        if (title) title.text = s.won ? "Victory!" : "Defeat";
        if (amountLine) amountLine.text = (gained >= 0) ? $"+{gained} Essence" : $"{gained} Essence";

        // Simple readable line (matches our RewardCalculator signals)
        if (detailLine)
            detailLine.text = $"Waves {s.wavesCleared}  •  Lives {s.livesEnd}/{s.livesStart}  •  Bosses {s.bossesKilled}  •  Diff {s.difficultyTier}";
    }

    // Optional: button hook
    public void OnContinue()
    {
        Destroy(gameObject);
        // Load menu or next flow...
    }
}
