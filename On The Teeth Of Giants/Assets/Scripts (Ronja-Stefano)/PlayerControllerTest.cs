using UnityEngine;

public class PlayerController : MonoBehaviour
{
    public TongueReceiver tongue;   // drag your TongueInput GameObject here in the Inspector
    public float moveSpeed = 5f;

    void Update()
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
    }
}
