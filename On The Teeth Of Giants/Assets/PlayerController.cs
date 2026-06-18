using UnityEngine;

public class PlayerController : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    [SerializeField]
    Rigidbody2D rb;

    [SerializeField]
    float movementspeed = 10f;

    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        /*
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");

        //Vector3 tempVect = new Vector3(h, v, 0);
        //tempVect = tempVect.normalized * movementspeed * Time.deltaTime;
        //rb.MovePosition(rb.transform.position + tempVect);
        */


    }

    private void FixedUpdate()
    {
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");

        Vector3 tempVect = new Vector3(h, v, 0);
        tempVect = tempVect.normalized * movementspeed * Time.deltaTime;
        rb.MovePosition(rb.transform.position + tempVect);
    }
}
