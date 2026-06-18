using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class CountdownTimer : MonoBehaviour
{
    public float timeRemaining = 60; // Set the initial time in seconds
    public bool timerIsRunning = false;
    public TextMeshProUGUI timeText; // Reference to the UI Text component

    void Start()
    {
        // Start the timer
        timerIsRunning = true;
    }

    void Update()
    {
        if (timerIsRunning)
        {
            if (timeRemaining > 0)
            {
                // Decrease the time remaining
                timeRemaining -= Time.deltaTime;
                DisplayTime(timeRemaining);
            }
            else
            {
                // Time has run out
                Debug.Log("Time has run out!");
                timeRemaining = 0;
                timerIsRunning = false;
                SceneManager.LoadScene(2); // Load the Game Over scene
            }
        }
    }

    void DisplayTime(float timeToDisplay)
    {
        // Convert the time to minutes and seconds
        timeToDisplay += 1;
        float minutes = Mathf.FloorToInt(timeToDisplay / 60);
        float seconds = Mathf.FloorToInt(timeToDisplay % 60);

        // Update the UI Text component
        timeText.text = string.Format("{0:00}:{1:00}", minutes, seconds);
    }
}