using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Globalization;
using System.Threading;
using UnityEngine;

// Receives "dx,dy,conf" UDP datagrams from the Python tongue sidecar and
// exposes the latest values + a direction. Add this to any GameObject.
// Python is the sender; this script is the listener, so it binds the port
// locally and does NOT need the Python PC's IP.
public class TongueReceiver : MonoBehaviour
{
    [Header("Network")]
    public int port = 5005;                 // must match UNITY_PORT in tongue_sidecar.py

    [Header("Latest values (read-only)")]
    public float dx;
    public float dy;
    public float conf;
    public string direction = "closed";     // up / down / left / right / closed

    UdpClient _client;
    Thread _thread;
    volatile bool _running;
    readonly object _lock = new object();
    float _dx, _dy, _conf;

    void Start()
    {
        _client = new UdpClient(port);      // binds 0.0.0.0:port -> any sender
        _running = true;
        _thread = new Thread(ReceiveLoop) { IsBackground = true };
        _thread.Start();
        Debug.Log($"TongueReceiver listening on UDP {port}");
    }

    void ReceiveLoop()
    {
        var remote = new IPEndPoint(IPAddress.Any, 0);
        while (_running)
        {
            try
            {
                byte[] data = _client.Receive(ref remote);          // blocks
                string msg = Encoding.ASCII.GetString(data);
                string[] p = msg.Split(',');
                if (p.Length >= 3 &&
                    float.TryParse(p[0], NumberStyles.Float, CultureInfo.InvariantCulture, out float ndx) &&
                    float.TryParse(p[1], NumberStyles.Float, CultureInfo.InvariantCulture, out float ndy) &&
                    float.TryParse(p[2], NumberStyles.Float, CultureInfo.InvariantCulture, out float nconf))
                {
                    lock (_lock) { _dx = ndx; _dy = ndy; _conf = nconf; }
                }
            }
            catch (SocketException) { /* socket closed on shutdown */ }
            catch (Exception e) { Debug.LogWarning("TongueReceiver: " + e.Message); }
        }
    }

    void Update()
    {
        lock (_lock) { dx = _dx; dy = _dy; conf = _conf; }
        direction = Classify(dx, dy, conf);
    }

    // Mirror of classify_direction() in tongue_colour.py: y grows downward,
    // the frame is mirrored so "left" is screen-left, conf <= 0 means closed.
    public static string Classify(float dx, float dy, float conf)
    {
        if (conf <= 0f) return "closed";
        if (Mathf.Abs(dx) >= Mathf.Abs(dy)) return dx > 0f ? "right" : "left";
        return dy > 0f ? "down" : "up";
    }

    void OnDisable()        { Shutdown(); }
    void OnApplicationQuit(){ Shutdown(); }

    void Shutdown()
    {
        _running = false;
        try { _client?.Close(); } catch { }
        try { _thread?.Join(200); } catch { }
    }
}
