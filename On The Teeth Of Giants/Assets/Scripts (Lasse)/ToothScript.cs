using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
                                    
public class ToothScript : MonoBehaviour
{
    public Gradient toothColor;

    [Range(0f, 1f)]
    public float colorValue = 0.0f;

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
        GetComponent<Image>().color = toothColor.Evaluate(colorValue);
    }

    public void Select()
    {
        Debug.Log("Selected tooth: " + gameObject.name);
        GetComponent<Image>().color = Color.red;
    }

    public void UnSelect()
    {
        Debug.Log("Unselected tooth: " + gameObject.name);
        GetComponent<Image>().color = toothColor.Evaluate(colorValue);
    }

    private void OnCollisionEnter2D(Collision2D collision)
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
    }
}
