using System;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using UnityEngine.UI;

// OPTIONAL. Connects to the Python sidecar's TCP video server and shows the
// webcam feed on a UI RawImage. Wire format per frame:
//   [4-byte big-endian length][JPEG bytes]   (see video_server.py)
// This script is the CLIENT, so it DOES need the Python PC's IP.
public class VideoReceiver : MonoBehaviour
{
    [Header("Network")]
    public string host = "127.0.0.1";       // same machine as the Python sidecar
    public int port = 5006;                 // must match VideoServer port

    [Header("Display")]
    public RawImage target; 
    public SpriteRenderer target2; 
    
    public float number1 = 1;
    public float number2 = 1;
    public float number3 = 1;
    public float number4 = 1;               // a UI RawImage to draw the feed onto

    TcpClient _client;
    NetworkStream _stream;
    Thread _thread;
    volatile bool _running;
    readonly object _lock = new object();
    byte[] _latestJpeg;
    Texture2D _tex;

    void Start()
    {
        _tex = new Texture2D(2, 2);
        _running = true;
        _thread = new Thread(ReceiveLoop) { IsBackground = true };
        _thread.Start();
    }

    void ReceiveLoop()
    {
        byte[] lenBuf = new byte[4];
        while (_running)
        {
            try
            {
                _client = new TcpClient();
                _client.Connect(host, port);
                _client.NoDelay = true;
                _stream = _client.GetStream();
                Debug.Log($"VideoReceiver connected to {host}:{port}");

                while (_running)
                {
                    ReadExactly(lenBuf, 4);
                    int len = (lenBuf[0] << 24) | (lenBuf[1] << 16) | (lenBuf[2] << 8) | lenBuf[3];
                    if (len <= 0 || len > 10_000_000) break;        // sanity guard
                    byte[] jpeg = new byte[len];
                    ReadExactly(jpeg, len);
                    lock (_lock) { _latestJpeg = jpeg; }
                }
            }
            catch (Exception) { /* fall through to reconnect */ }
            finally { try { _client?.Close(); } catch { } }

            if (_running) Thread.Sleep(500);                        // retry after a pause
        }
    }

    void ReadExactly(byte[] buf, int count)
    {
        int off = 0;
        while (off < count)
        {
            int n = _stream.Read(buf, off, count - off);
            if (n <= 0) throw new Exception("stream closed");
            off += n;
        }
    }

    void Update()
    {
        byte[] jpeg = null;
        lock (_lock) { if (_latestJpeg != null) { jpeg = _latestJpeg; _latestJpeg = null; } }
        if (jpeg != null && target != null)
        {
            _tex.LoadImage(jpeg);           // decode JPEG (main thread only)
            target.texture = _tex;
            RenderSprite(_tex);
        }
    }

    public void RenderSprite(Texture2D tex)
    {
        Sprite sprite = Sprite.Create(tex, new Rect(0, 0, tex.width * number1, tex.height * number2), new Vector2(0.5f * number3, 0.5f * number3));
        target2.sprite = sprite;
    }

    void OnDisable()        { Shutdown(); }
    void OnApplicationQuit(){ Shutdown(); }

    void Shutdown()
    {
        _running = false;
        try { _stream?.Close(); } catch { }
        try { _client?.Close(); } catch { }
        try { _thread?.Join(200); } catch { }
    }
}
