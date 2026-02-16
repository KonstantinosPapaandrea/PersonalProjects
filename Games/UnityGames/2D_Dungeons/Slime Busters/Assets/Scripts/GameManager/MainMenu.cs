using UnityEngine;
using UnityEngine.SceneManagement;

public class MainMenu : MonoBehaviour
{
    public void StartMenu()
    {
        // replace with the name of your game scene (must match exactly)
        SceneManager.LoadScene("MainMenu");
    }
    public void ChooseMap()
    {
        // replace with the name of your game scene (must match exactly)
        SceneManager.LoadScene("ChooseMap");
    }

    public void QuitGame()
    {
        Debug.Log("Quit Game"); // will show in Editor
        Application.Quit();     // works in build
    }
    public void BackToMainMenu()
    {
        // replace with the name of your game scene (must match exactly)
        SceneManager.LoadScene("StartMenu");
    }

    public void Lab()
    {
        // replace with the name of your game scene (must match exactly)
        SceneManager.LoadScene("Lab");
    }

}
