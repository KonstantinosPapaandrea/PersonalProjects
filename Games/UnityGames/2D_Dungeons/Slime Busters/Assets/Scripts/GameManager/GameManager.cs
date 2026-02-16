using UnityEngine;
using TMPro;
using System;
using UnityEngine.SceneManagement;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance;
    public CanvasGroup gameOver;

    [Header("Stats")]
    public int coins = 300;
    public int lives = 100;

    [Header("UI")]
    public TMP_Text coinsText;
    public TMP_Text livesText;

    public Action onCoinsChanged;

    // NEW: guard
    public bool IsGameOver { get; private set; }

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
    }

    void Start()
    {
        // NEW: ensure normal time and hidden panel at run start
        Time.timeScale = 1f;
        SetGameOverUI(false);
        RefreshAllUI();
        GameSignals.ResetStickyFlags();

    }

    public void AddCoins(int amount)
    {
        coins += amount;
        UpdateCoinsUI();
    }

    public bool SpendCoins(int amount)
    {
        if (coins < amount) return false;
        coins -= amount;
        UpdateCoinsUI();
        return true;
    }

    public void LoseLife(int amount)
    {
        if (IsGameOver) return; // NEW: ignore after game over
        lives = Mathf.Max(0, lives - amount);
        UpdateLivesUI();
        if (lives <= 0) GameOver();
    }

    void UpdateCoinsUI()
    {
        if (coinsText) coinsText.text = "Gold: " + coins.ToString();
        onCoinsChanged?.Invoke();
    }

    void UpdateLivesUI()
    {
        if (livesText) livesText.text = "Lives: " + lives.ToString();
    }

    void RefreshAllUI()
    {
        UpdateCoinsUI();
        UpdateLivesUI();
    }

    public bool CanAfford(int cost) => coins >= cost;

    // NEW: central UI toggle
    void SetGameOverUI(bool on)
    {
        if (!gameOver) return;
        gameOver.alpha = on ? 1f : 0f;
        gameOver.interactable = on;
        gameOver.blocksRaycasts = on;
    }

    // UPDATED: guarded, signals, time freeze, ui
    void GameOver()
    {
        if (IsGameOver) return;
        IsGameOver = true;

        Debug.Log("[GM] GameOver()");
        GameSignals.RaiseDefeat();   // ← must log "[SIG] DEFEAT raised"
        Time.timeScale = 0f;
        SetGameOverUI(true);
    }


    // NEW: hook these to your Game Over UI buttons
    public void RestartLevel()
    {
        Time.timeScale = 1f;
        Scene current = SceneManager.GetActiveScene();
        SceneManager.LoadScene(current.buildIndex);
    }

    public void ReturnToMenu()
    {
        Time.timeScale = 1f;
        // change to your menu scene name/index:
        SceneManager.LoadScene("MainMenu");
    }
}
