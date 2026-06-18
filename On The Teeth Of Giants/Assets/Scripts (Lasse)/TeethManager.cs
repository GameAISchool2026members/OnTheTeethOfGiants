
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

public class TeethManager : MonoBehaviour
{
    List<GameObject> teeth = new List<GameObject>();
    //GameObject selected;

    public static UnityEvent onToothCleaned = new UnityEvent();

    [Range(0f, 1f)]
    public float teethOccurenceRate = 0.5f;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        teeth = new List<GameObject>(GameObject.FindGameObjectsWithTag("Tooth"));
        //selected = EventSystem.current.currentSelectedGameObject;
        /*Debug.Log($"Selected: {selected}");
        if (selected == null)
        {
            Debug.Log("Selected is null, selecting first tooth");
            selected = teeth.FirstOrDefault();
            selected.GetComponent<ToothScript>().Select();
        } */
        InitializeTeethColour();
        onToothCleaned.AddListener(OnCleaned);

    }

    public void InitializeTeethColour()
    {
        foreach (GameObject tooth in teeth)
        {
            float randomValue = Random.Range(0f, 1f);
            if (randomValue < teethOccurenceRate)
            {
                Debug.Log("Tooth " + tooth.name + " is affected (random value: " + randomValue + ")");
                tooth.GetComponent<ToothScript>().EvaluateColor(1f);
                tooth.GetComponent<ToothScript>().isYellow = true;
            }
            else
            {
                Debug.Log("Tooth " + tooth.name + " is healthy (random value: " + randomValue + ")");
                tooth.GetComponent<ToothScript>().EvaluateColor(0f);
                tooth.GetComponent<ToothScript>().isYellow = false;
            }
        }
    }

    public void OnCleaned()
    {
        if (teeth.Any(x => x.GetComponent<ToothScript>().isYellow))
        {
            Debug.Log("Not all teeth are clean yet.");
            return;
        }

        SceneManager.LoadScene(1);
    }

    #region OLD VERSION
    
    /*public void MoveRight()
    {
        Debug.Log("MoveRight");
        selected.GetComponent<ToothScript>().UnSelect();
        int index = teeth.Any(x => x == selected) ? teeth.IndexOf(selected) : -1;
        if (index < teeth.Count - 1)
        {
            selected = teeth[index + 1];
            selected.GetComponent<ToothScript>().Select();
        }
    }

    public void MoveLeft()
    {
        Debug.Log("MoveLeft");
        selected.GetComponent<ToothScript>().UnSelect();
        int index = teeth.Any(x => x == selected) ? teeth.IndexOf(selected) : -1;
        if (index > 0)
        {
            selected = teeth[index - 1];
            selected.GetComponent<ToothScript>().Select();
        }
    }

    // Update is called once per frame
    void Update()
    {
        if (Keyboard.current.leftArrowKey.wasPressedThisFrame)
        {
            MoveLeft();
        }
        if (Keyboard.current.rightArrowKey.wasPressedThisFrame)
        {
            MoveRight();
        }
    } */
    #endregion
}
