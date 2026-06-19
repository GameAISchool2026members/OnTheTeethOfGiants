using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;

public class WinLoop : MonoBehaviour
{
    private float delayTime;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        delayTime = 5;
        startDelay(delayTime);
    }

    void startDelay(float delayTime)
    {
        StartCoroutine(delay(delayTime));
    }

    IEnumerator delay(float delayTime)
    {
        yield return new WaitForSeconds(delayTime);
        SceneManager.LoadScene(3);
    }

    // Update is called once per frame
    void Update()
    {
        
    }
}
