using JetBrains.Annotations;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ToothScript : MonoBehaviour
{
    public Gradient toothColor;

    [Range(0f, 1f)]
    public float colorValue = 0.0f;

    [Range(0f, 10f)]
    public int toothDecayTime = 5;
    public int timeUntilDecayStarts = 2;

    public bool isWhite;
    public bool isYellow;
    public bool isBlack;
    public bool isGold;

    public Material gold;

    // NEW: Track if this specific tooth is actively in the process of rotting
    private bool isDecaying = false;

    Coroutine toothDecayRoutine;
    List<ToothScript> neighborTeeth;

    void Start()
    {
        neighborTeeth = FindNeighborsPhysics();
        White();
    }

    public void EvaluateColor(float value)
    {
        colorValue = Mathf.Clamp01(value);
        GetComponent<SpriteRenderer>().color = toothColor.Evaluate(value);
    }

    public void Clean()
    {
        if (isYellow)
        {
            Debug.Log("Cleaned tooth: " + gameObject.name);
            White();
            // Assuming TeethManager handles this event statically
            TeethManager.onToothCleaned.Invoke(); 
        }
    }

    public void LootBox()
    {
        Debug.Log("Lets goooo");
    }

    void OnTriggerEnter2D(Collider2D other)
    {
        if (other.gameObject.CompareTag("Player"))
        {
            if (isYellow)
            {
                Clean();
            }
            else if (isBlack || isDecaying)
            {
                StopToothDecay();
            }
            else if (isGold)
            {
                LootBox();
            }
        }
    }

    public void Yellow()
    {
        EvaluateColor(1f);
        isYellow = true;
        isWhite = false;
        isBlack = false;
    }

    public void White()
    {
        EvaluateColor(0f);
        isWhite = true;
        isYellow = false;
        isBlack = false;
        isDecaying = false;
    }

    public void Black()
    {
        isBlack = true;
        isYellow = false;
        isWhite = false;
        isDecaying = false;
        GetComponent<SpriteRenderer>().color = Color.black;

        foreach (var n in neighborTeeth)
        {
            if (!n.isBlack && !n.isDecaying)
            {
                n.StartDecay();
            }
        }
    }

    public void Gold()
    {
        isBlack = false;
        isYellow = false;
        isWhite = false;
        GetComponent<SpriteRenderer>().material = gold;
    }

    public void StartDecay()
    {
        if (toothDecayRoutine != null)
        {
            StopCoroutine(toothDecayRoutine);
        }

        isDecaying = true;
        toothDecayRoutine = StartCoroutine(BlackToothDecay());
    }

    public IEnumerator BlackToothDecay()
    {
        yield return new WaitForSeconds(timeUntilDecayStarts);

        float elapsedTime = 0;
        while (elapsedTime < toothDecayTime)
        {
            elapsedTime += Time.deltaTime;
            float t = elapsedTime / toothDecayTime;

            GetComponent<SpriteRenderer>().color = Color.Lerp(Color.white, Color.black, t);
            yield return null;
        }

        Black();
    }

    public void StopToothDecay()
    {
        if (toothDecayRoutine != null)
        {
            StopCoroutine(toothDecayRoutine);
            toothDecayRoutine = null;
        }

        White();

        foreach (var n in neighborTeeth)
        {
            if (n.isDecaying)
            {
                n.StopToothDecay();
            }
        }
    }

    public List<ToothScript> FindNeighborsPhysics()
    {
        List<ToothScript> foundNeighbors = new List<ToothScript>();
        float checkRadius = 7.5f; // After testing this number is just right
        Collider2D[] colliders = Physics2D.OverlapCircleAll(transform.position, checkRadius);

        foreach (var col in colliders)
        {
            if (col.gameObject == this.gameObject) continue;

            ToothScript neighbor = col.GetComponent<ToothScript>();
            if (neighbor != null)
            {
                foundNeighbors.Add(neighbor);
            }
        }
        return foundNeighbors;
    }
}