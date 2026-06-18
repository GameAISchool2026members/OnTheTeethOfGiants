using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.Timeline;
using UnityEngine.UI;

public class ToothScript : MonoBehaviour
{
    public Gradient toothColor;

    [Range(0f, 1f)]
    public float colorValue = 0.0f;

    public bool isWhite;
    public bool isYellow;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        //EvaluateColor(colorValue);
    }

    public void EvaluateColor(float value)
    {
        colorValue = Mathf.Clamp01(value);
        GetComponent<SpriteRenderer>().color = toothColor.Evaluate(value);
    }

    /*public void Select()
    {
        Debug.Log("Selected tooth: " + gameObject.name);
        GetComponent<SpriteRenderer>().color = Color.red;
    }

    public void UnSelect()
    {
        Debug.Log("Unselected tooth: " + gameObject.name);
        GetComponent<SpriteRenderer>().color = toothColor.Evaluate(colorValue);
    }*/

    public void Clean()
    {
        if (isYellow)
        {
            Debug.Log("Cleaned tooth: " + gameObject.name);
            EvaluateColor(0f);
            White();
            TeethManager.onToothCleaned.Invoke();
        }
    }

    void OnTriggerEnter2D(Collider2D other)
    {
        if (other.gameObject.CompareTag("Player"))
        {
            Clean();
        }
    }

    /*void OnTriggerExit2D(Collider2D other)
    {
        if (other.gameObject.CompareTag("Player"))
        {
            UnSelect();
        }
    }*/

    public void Yellow()
    {
        isYellow = true;
        isWhite = false;
    }

    public void White()
    {
        isWhite = true;
        isYellow = false;
    }

    // OLD VERSION
    /*private void OnCollisionEnter2D(Collision2D collision)
    {
        if (collision.gameObject == GameObject.FindGameObjectWithTag("Player"))
        {
            Select();
        }
    }

    private void OnCollisionExit2D(Collision2D collision)
    {
        if (collision.gameObject == GameObject.FindGameObjectWithTag("Player"))
        {
            UnSelect();
        }
    }*/
}
