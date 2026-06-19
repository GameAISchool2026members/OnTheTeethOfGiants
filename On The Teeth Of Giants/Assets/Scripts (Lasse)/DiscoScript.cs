using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

public class DiscoScript : MonoBehaviour
{
    Image img;
    TeethManager manager;
    SpriteRenderer sr;

    [Range(0f, 1f)]
    public float pace = 1f;

    public bool beam;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        img = GetComponent<Image>();
        manager = GameObject.FindGameObjectWithTag("TeethManager").GetComponent<TeethManager>();
        sr = GetComponent<SpriteRenderer>();
    }

    // Update is called once per frame
    void Update()
    {
        if (manager != null && manager.overdriveActive && !beam)
        {
            DiscoTime();
        }
        else if (manager != null && manager.overdriveActive && beam)
        {
            Beam();
        }
    }

    public void DiscoTime()
    {
            Color c = Color.HSVToRGB(DateTime.Now.Millisecond * 0.001f, 1, 1) * pace;
            c.a = 0.2f;
            img.color = c;
    }

    public void Beam()
    {
        Color c = Color.HSVToRGB(DateTime.Now.Millisecond * 0.001f, 1, 1) * pace;
        c.a = 0.3f;
        sr.color = c;
    }
}
