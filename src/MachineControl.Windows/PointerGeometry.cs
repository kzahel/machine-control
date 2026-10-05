namespace MachineControl.Windows;

/// Geometry shared by admission and dispatch. Coordinates remain physical
/// pixels, including negative origins; a virtual-screen gap is not a display.
internal static class PointerGeometry
{
    internal static bool Intersects(int x, int y, int x2, int y2,
        double left, double top, double right, double bottom)
    {
        if (right <= left || bottom <= top) return false;
        double min = 0, max = 1;
        bool Clip(double origin, double delta, double low, double high)
        {
            if (delta == 0) return origin >= low && origin < high;
            var a = (low - origin) / delta;
            var b = (high - origin) / delta;
            min = Math.Max(min, Math.Min(a, b));
            max = Math.Min(max, Math.Max(a, b));
            return min <= max;
        }
        return Clip(x, (double)x2 - x, left, right) &&
            Clip(y, (double)y2 - y, top, bottom);
    }
}
