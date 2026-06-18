using NUnit.Framework;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using System.Collections.Generic;
using System.Linq;

public class TeethManager : MonoBehaviour
{
    List<GameObject> teeth = new List<GameObject>();
    GameObject selected;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        teeth = new List<GameObject>(GameObject.FindGameObjectsWithTag("Tooth"));
        selected = EventSystem.current.currentSelectedGameObject;
        Debug.Log($"Selected: {selected}");
        if (selected == null)
        {
            Debug.Log("Selected is null, selecting first tooth");
            selected = teeth.FirstOrDefault();
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
    }



    public void MoveRight()
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
}
