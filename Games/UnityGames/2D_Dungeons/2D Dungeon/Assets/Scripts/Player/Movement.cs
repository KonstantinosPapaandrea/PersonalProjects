using System.Collections;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public class Movement : MonoBehaviour
{
    Rigidbody2D rb;
    Vector2 Coords = Vector2.zero;
    [SerializeField] float speed = 5f;
    [SerializeField] Camera camera;
    void Awake() => rb = GetComponent<Rigidbody2D>();

    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void FixedUpdate()
    {
        Vector3 offset = new Vector3(0, 0, -5);
        camera.transform.position=this.transform.position+offset;

        rb.velocityX = Input.GetAxis("Horizontal")*speed;
        rb.velocityY = Input.GetAxis("Vertical")*speed;
    
    
    }
}
