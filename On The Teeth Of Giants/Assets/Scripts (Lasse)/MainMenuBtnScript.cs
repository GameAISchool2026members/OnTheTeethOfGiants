using System.Collections;
using System.Reflection.Metadata;
using TMPro;
using Unity.Jobs;
using UnityEngine;
using UnityEngine.SceneManagement;

public class MainMenuBtnScript : MonoBehaviour
{
    public TextMeshProUGUI tongueInstruction;

    public bool isStart;

    Vector3 initSize;

    bool isInside;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        initSize = transform.localScale;
    }

    // Update is called once per frame
    void Update()
    {
    }

    private void OnTriggerEnter2D(Collider2D collision)
    {
        tongueInstruction.text = "STICK YOUR TONGUE OUT TO CONFIRM";
        if (isStart)
        {
            StartCoroutine(StartGameConfirmation());
        }
        else if (!isStart)
        {
            StartCoroutine(QuitGameConfirmation());
        }
    }

    private void OnTriggerExit2D(Collider2D collision)
    {
        tongueInstruction.text = "MOVE YOUR TONGUE TO NAVIGATE";
        StopAllCoroutines();
        ResetSizes();
    }

    public IEnumerator StartGameConfirmation()
    {
        float elapsedTime = 0;
        while (elapsedTime < 2f)
        {
            elapsedTime += Time.deltaTime;
            float t = elapsedTime / 2f;
            float scale = Mathf.Lerp(1, 2, t);
            transform.localScale = initSize * scale;
            yield return null;
        }
        transform.localScale = initSize * 2;
        SceneManager.LoadScene(0);
    }

    public IEnumerator QuitGameConfirmation()
    {
        float elapsedTime = 0;
        while (elapsedTime < 2f)
        {
            elapsedTime += Time.deltaTime;
            float t = elapsedTime / 2f;
            float scale = Mathf.Lerp(1, 2, t);
            transform.localScale = initSize * scale;
            yield return null;
        }
        transform.localScale = initSize * 2;
        Application.Quit();
    }

    public void ResetSizes()
    {
        transform.localScale = initSize;
    }
}
