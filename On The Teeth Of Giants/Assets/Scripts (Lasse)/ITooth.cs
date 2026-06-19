using UnityEngine;

public enum ToothType
{
    White = 0,
    Gold = 1,
    Diamond = 2,
    Rotten = 3,
    Wormhole = 4,
    Cracked = 5
}

public interface ITooth
{
    public ToothType ToothType { get; set; }
    public GameObject ToothSprite { get; set; }
    public void InitializeTooth(ToothType toothType);
    public void OnClean();
}
