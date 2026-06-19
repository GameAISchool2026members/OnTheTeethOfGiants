using JetBrains.Annotations;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
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
    public Sprite WhiteTooth;
    public bool isYellow;
    public Sprite YellowTooth;
    public bool isBlack;
    public Sprite BlackTooth;
    public bool isGold;
    public Sprite GoldTooth;
    public bool isOverdrive;
    public Sprite OverdriveTooth;

    public bool isPortal;
    public Sprite PortalTooth;

    List<GameObject> teeth;

    // NEW: Track if this specific tooth is actively in the process of rotting
    private bool isDecaying = false;

    Coroutine toothDecayRoutine;
    List<ToothScript> neighborTeeth;

    TeethManager TeethManager;

    void Start()
    {
        neighborTeeth = FindNeighborsPhysics();
        White();
        TeethManager = GameObject.FindGameObjectWithTag("TeethManager").GetComponent<TeethManager>();
    }

    public void EvaluateColor(float value)
    {
        colorValue = Mathf.Clamp01(value);
        GetComponent<SpriteRenderer>().color = toothColor.Evaluate(value);
    }

    public void Clean()
    {
        /*if (isYellow)
        {
            Debug.Log("Cleaned tooth: " + gameObject.name);
            White();
            // Assuming TeethManager handles this event statically
            TeethManager.onToothCleaned.Invoke(); 
        }*/
        if (isYellow)
        {
            // Black Already Works
            White();
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
            TeethManager.OnCleaned();
            if (isYellow)
            {
                Clean();
            }
            else if (isBlack || isDecaying)
            {
                StopToothDecay();
                White();
            }
            else if (isGold)
            {
                LootBox();
                White();
            }
            else if (isOverdrive)
            {
                TeethManager.EnableOverdrive();
                White();
            }
            else if (isPortal)
            {
                DoPortalThing(other.gameObject);
            }
        }
    }

    public void Yellow()
    {
        //EvaluateColor(1f);
        isYellow = true;
        isWhite = false;
        isBlack = false;
        isOverdrive = false;
        isPortal = false;
        isGold = false;
        GetComponent<SpriteRenderer>().sprite = YellowTooth;
    }

    public void White()
    {
        //EvaluateColor(0f);

        isWhite = true;
        isYellow = false;
        isBlack = false;
        isDecaying = false;
        isOverdrive = false;
        isPortal = false;
        isGold = false;
        GetComponent<SpriteRenderer>().sprite = WhiteTooth;

    }

    public void Black()
    {
        isBlack = true;
        isYellow = false;
        isWhite = false;
        isDecaying = false;
        isOverdrive = false;
        isPortal = false;
        isGold = false;
        //GetComponent<SpriteRenderer>().color = Color.black;
        GetComponent<SpriteRenderer>().sprite = BlackTooth;

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
        isGold = true;
        isBlack = false;
        isYellow = false;
        isWhite = false;
        isPortal = false;
        isOverdrive = false;
        GetComponent<SpriteRenderer>().sprite = GoldTooth;
    }

    public void Overdrive()
    {
        isOverdrive = true;
        isWhite = false;
        isYellow = false;
        isBlack = false;
        isDecaying = false;
        isGold = false;
        isPortal = false;
        GetComponent<SpriteRenderer>().sprite = OverdriveTooth;
    }

    public void Portal()
    {
        isPortal = true;
        isOverdrive = false;
        isWhite = false;
        isYellow = false;
        isBlack = false;
        isDecaying = false;
        isGold = false;
        GetComponent<SpriteRenderer>().sprite = PortalTooth;
    }

    public void DoPortalThing(GameObject enteredTooth)
    {
        Debug.Log("Tooth1" + enteredTooth.transform.position);
        Debug.Log("Doing Portal Thing");
        //GameObject OtherTooth = TeethManager.currentPortalTeeth.Where<GameObject>(x => x.gameObject != enteredTooth);
        GameObject OtherTooth = null;
        foreach(GameObject tooth in TeethManager.currentPortalTeeth)
        {
            if (tooth != enteredTooth)
            {
                OtherTooth = tooth;
                Debug.Log("Tooth2" + OtherTooth.transform.position);
            }

        }
        foreach(var t in TeethManager.currentPortalTeeth)
        {
            t.GetComponent<ToothScript>().White();
        }
        GameObject.FindWithTag("Player").transform.position = OtherTooth.transform.position;
        TeethManager.currentPortalTeeth.Clear(); 
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
        GetComponent<SpriteRenderer>().color = Color.white;
        GetComponent<SpriteRenderer>().sprite = BlackTooth;
        Black();
    }

    public void StopToothDecay()
    {
        Debug.Log("Stopping Tooth Decay");
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