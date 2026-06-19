using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;

public class TeethManager : MonoBehaviour
{
    private List<GameObject> teeth = new List<GameObject>();

    public static UnityEvent onToothCleaned = new UnityEvent();

    [Range(0f, 1f)]
    public float teethOccurenceRate = 0.5f;

    [Range(5f, 20f)]
    public int timeToRotten = 10;

    [Range(0f, 1f)]
    public float goldenTeethProbability = 0.1f;

    void Start()
    {
        teeth = new List<GameObject>(GameObject.FindGameObjectsWithTag("Tooth"));

        InitializeTeethColour();

        onToothCleaned.AddListener(OnCleaned);

        StartCoroutine(RottenTeeth());
    }

    void OnDestroy()
    {
        onToothCleaned.RemoveListener(OnCleaned);
    }

    public void InitializeTeethColour()
    {
        foreach (GameObject tooth in teeth)
        {
            ToothScript script = tooth.GetComponent<ToothScript>();
            if (script == null) continue;

            float randomValue = Random.Range(0f, 1f);
            if (randomValue < teethOccurenceRate)
            {
                Debug.Log($"Tooth {tooth.name} is affected (random value: {randomValue})");
                script.Yellow();
            }
            else
            {
                Debug.Log($"Tooth {tooth.name} is healthy (random value: {randomValue})");
                script.White();
            }
        }
    }

    public IEnumerator RottenTeeth()
    {
        while (true)
        {
            yield return new WaitForSeconds(timeToRotten);

            List<GameObject> validTeeth = teeth.Where(t => {ToothScript script = t.GetComponent<ToothScript>(); return script != null && !script.isBlack; }).ToList();

            if (validTeeth.Count > 0)
            {
                int randomIndex = Random.Range(0, validTeeth.Count);
                ToothScript targetTooth = validTeeth[randomIndex].GetComponent<ToothScript>();
                if (GoldTooth())
                {
                    targetTooth.Gold();
                }
                else
                {
                    targetTooth.Black();
                }
            }
            else
            {
                Debug.Log("All teeth are black");
            }
        }
    }

    public bool GoldTooth()
    {
        int randomNumber = Random.Range(0, 1);
        if (randomNumber < goldenTeethProbability)
        {
            return true;
        }
        return false;
    }

    public void OnCleaned()
    {
        if (teeth.Any(x => {ToothScript script = x.GetComponent<ToothScript>(); return script != null && script.isYellow;}))
        {
            Debug.Log("Not all teeth are clean yet.");
            return;
        }

        Debug.Log("You Win");
        SceneManager.LoadScene(1);
    }
}