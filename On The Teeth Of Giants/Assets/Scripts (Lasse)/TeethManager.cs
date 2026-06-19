using NUnit.Framework.Interfaces;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class TeethManager : MonoBehaviour
{
    private List<GameObject> teeth = new List<GameObject>();

    public static UnityEvent onToothCleaned = new UnityEvent();

    [Range(0f, 1f)]
    public float teethOccurenceRate = 0.5f;

    [Header("Timers")]
    public int timeToRotten = 10;
    public int timeToDisco = 10;
    public int timeToPortal = 10;

    [Range(0f, 1f)]
    public float goldenTeethProbability = 0.1f;
    [Range(0f, 1f)]
    public float overdriveTeethProbability = 0.1f;
    [Range(0f, 1f)]
    public float portalTeethProbability = 0.05f;

    [SerializeField] float overdriveMultiplier = 2f;
    [SerializeField] float overdriveDuration = 5f;


    [Header("Overdrive Settings")]
    public bool overdriveActive = false;

    PlayerController player;

    public GameObject overdriveScreen;
    public GameObject beam1;
    public GameObject beam2;

    public List<GameObject> currentPortalTeeth = new List<GameObject>();

    void Start()
    {
        teeth = new List<GameObject>(GameObject.FindGameObjectsWithTag("Tooth"));
        player = GameObject.FindGameObjectWithTag("Player").GetComponent<PlayerController>();

        InitializeTeethColour();

        onToothCleaned.AddListener(OnCleaned);

        StartCoroutine(RottenTeeth());
        StartCoroutine(GoldTeeth());
        StartCoroutine(PortalTeeth());
        StartCoroutine(OverdriveTeeth());
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

            List<GameObject> validTeeth = teeth.Where(t => {ToothScript script = t.GetComponent<ToothScript>(); return script != null && script.isWhite; }).ToList();

            if (validTeeth.Count > 0)
            {
                int randomIndex = Random.Range(0, validTeeth.Count);
                ToothScript targetTooth = validTeeth[randomIndex].GetComponent<ToothScript>();

                targetTooth.Black();
            }
            else
            {
                Debug.Log("All teeth are black");
            }
        }
    }

    public IEnumerator OverdriveTeeth()
    {
        while (true)
        {
            yield return new WaitForSeconds(timeToDisco);

            List<GameObject> validTeeth = teeth.Where(t => { ToothScript script = t.GetComponent<ToothScript>(); return script != null && script.isWhite; }).ToList();

            if (validTeeth.Count > 0)
            {
                int randomIndex = Random.Range(0, validTeeth.Count);
                ToothScript targetTooth = validTeeth[randomIndex].GetComponent<ToothScript>();

                if (OverdriveTooth())
                {
                    targetTooth.Overdrive();
                }
            }
            else
            {
                Debug.Log("All teeth are black");
            }
        }
    }

    public IEnumerator PortalTeeth()
    {
        while (true)
        {
            yield return new WaitForSeconds(timeToPortal);

            List<GameObject> validTeeth = teeth.Where(t => { ToothScript script = t.GetComponent<ToothScript>(); return script != null && script.isWhite; }).ToList();

            if (validTeeth.Count > 0)
            {
                if (currentPortalTeeth.Count == 0)
                {
                    List<GameObject> portalTeeth = PortalSetup();
                    currentPortalTeeth = portalTeeth;

                    if (PortalTooth())
                    {
                        foreach (var tooth in portalTeeth)
                        {
                            tooth.GetComponent<ToothScript>().Portal();
                        }
                    }
                }
                //int randomIndex = Random.Range(0, validTeeth.Count);
                //ToothScript targetTooth = validTeeth[randomIndex].GetComponent<ToothScript>(); 
            }
            else
            {
                Debug.Log("All teeth are black");
            }
        }
    }

    public IEnumerator GoldTeeth()
    {
        while (true)
        {
            yield return new WaitForSeconds(timeToRotten);

            List<GameObject> validTeeth = teeth.Where(t => { ToothScript script = t.GetComponent<ToothScript>(); return script != null && script.isWhite; }).ToList();

            if (validTeeth.Count > 0)
            {
                int randomIndex = Random.Range(0, validTeeth.Count);
                ToothScript targetTooth = validTeeth[randomIndex].GetComponent<ToothScript>();

                if (GoldTooth())
                {
                    targetTooth.Gold();
                }
            }
            else
            {
                Debug.Log("All teeth are black");
            }
        }
    }
    public List<GameObject> PortalSetup()
    {
        int randomIndex;
        do
        {
            randomIndex = Random.Range(0, teeth.Count);
        }
        while (!teeth[randomIndex].GetComponent<ToothScript>().isWhite);
        GameObject firstTooth = teeth[randomIndex];
        int randomIndex2 = Random.Range(0, teeth.Count);
        do
        {
            randomIndex2 = Random.Range(0, teeth.Count);
        }
        while (!teeth[randomIndex2].GetComponent<ToothScript>().isWhite && !(firstTooth));
        GameObject secondTooth = teeth[randomIndex2];

        return new List<GameObject>()
        {
            firstTooth,
            secondTooth
        };

    }

   

    public bool GoldTooth()
    {
        return false; // Not implemented as of now
        int randomNumber = Random.Range(0, 1);
        if (randomNumber < goldenTeethProbability)
        {
            return true;
        }
        return false;
    }

    public bool OverdriveTooth()
    {
        int randomNumber = Random.Range(0, 1);
        if (randomNumber < overdriveTeethProbability)
        {
            return true;
        }
        return false;
    }
    public bool PortalTooth()
    {
        int randomNumber = Random.Range(0, 1);
        if (randomNumber < portalTeethProbability)
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

    public void EnableOverdrive()
    {
        overdriveScreen.SetActive(true);
        beam1.SetActive(true);
        beam2.SetActive(true);
        overdriveActive = true;
        //float newMoveSpeed = Mathf.Clamp(overdriveMultiplier * player.moveSpeed, player.startMoveSpeed, overdriveMultiplier);
        player.moveSpeed *= overdriveMultiplier;
        StartCoroutine(Overdrive());
    }

    public IEnumerator Overdrive()
    {
        yield return new WaitForSeconds(overdriveDuration);
        DisableOverdrive();
    }

    public void DisableOverdrive()
    {
        overdriveScreen.SetActive(false);
        beam1.SetActive(false);
        beam2.SetActive(false);
        overdriveActive = false;
        player.ResetSpeed();
        StopAllCoroutines();
    }


}