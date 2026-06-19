using System;
using System.Collections;
using Unity.Burst;
using UnityEngine;
using UnityEngine.UIElements;

public class PlayerController : MonoBehaviour
{
    public TongueReceiver tongue;   // drag your TongueInput GameObject here in the Inspector
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    [SerializeField]
    Rigidbody2D rb;

    [SerializeField]
    public float moveSpeed = 10f;

    float startMoveSpeed;
    

    void Start()
    {
        startMoveSpeed = moveSpeed;
    }

    private void FixedUpdate()
    {
        if (tongue == null) return;

        Vector3 move = Vector3.zero;

        switch (tongue.direction)
        {
            case "up":
                move = Vector3.up;
                break;
            case "down":
                move = Vector3.down;
                break;
            case "left":
                move = Vector3.left;
                break;
            case "right":
                move = Vector3.right;
                break;
            case "closed":
                // no input, stay still
                break;
        }

        transform.position += move * moveSpeed * Time.deltaTime;

        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");

        Vector3 tempVect = new Vector3(h, v, 0);
        tempVect = tempVect.normalized * moveSpeed * Time.deltaTime;
        rb.MovePosition(rb.transform.position + tempVect);
    }

    public void ResetSpeed()
    {
        moveSpeed = startMoveSpeed;
    }
}
