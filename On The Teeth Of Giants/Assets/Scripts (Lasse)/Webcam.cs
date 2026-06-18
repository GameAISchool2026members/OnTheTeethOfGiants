using UnityEngine;
using UnityEngine.UI;

public class Webcam : MonoBehaviour
{
    WebCamDevice webCamDevice;
    RawImage rawImage;
    WebCamTexture webCamTexture;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        webCamDevice = WebCamTexture.devices[0];
        webCamTexture = new WebCamTexture(webCamDevice.name, 640, 480);
        rawImage = GetComponent<RawImage>();
        rawImage.texture = webCamTexture;
        webCamTexture.Play();
    }

    // Update is called once per frame
    void Update()
    {
        
    }
}
