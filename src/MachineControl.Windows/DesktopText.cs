using System.Runtime.InteropServices;

namespace MachineControl.Windows;

/// Typed-text delivery. Characters the receiving keyboard layout can produce
/// are sent as layout keystrokes, the rest as Unicode packets; see
/// TextStrokes for why.
internal static partial class DesktopController
{
    private const ushort ShiftKey = 0x10;

    /// What a typed text actually used, for the result.
    private sealed class TextDelivery
    {
        internal List<TextStroke> Strokes { get; } = [];
        internal string? PacketReason { get; set; }

        internal object Summary() => new
        {
            layoutKeystrokes = Strokes.Count(stroke => stroke.Layout),
            unicodePackets = Strokes.Count(stroke => !stroke.Layout),
            unicodeReason = PacketReason,
        };
    }

    /// Plans and sends one segment against the current receiver. Layout
    /// keystrokes are used only when they cannot be reinterpreted: no held
    /// modifier, Caps Lock off and no open input method, which would compose
    /// the keys.
    private static void SendTextSegment(string value, TextDelivery delivery)
    {
        if (value.Length == 0) return;
        var foreground = NativeMethods.GetForegroundWindow();
        var thread = NativeMethods.GetWindowThreadProcessId(foreground, out _);
        var layout = TextNative.GetKeyboardLayout(thread);
        var unavailable = LayoutUnavailable(foreground, thread, layout);
        delivery.PacketReason ??= unavailable;
        var strokes = TextStrokes.Plan(value, unavailable is null,
            character => TextNative.VkKeyScanExW(character, layout),
            (character, virtualKey, shift) => Produces(character, virtualKey, shift, layout));
        if (unavailable is null && strokes.Any(stroke => !stroke.Layout)) delivery.PacketReason ??= "not_on_layout";
        foreach (var stroke in strokes)
        {
            if (stroke.Layout) SendLayoutStroke(stroke, layout);
            else SendUnicodeSegment(stroke.Character.ToString());
            delivery.Strokes.Add(stroke);
        }
    }

    private static string? LayoutUnavailable(IntPtr foreground, uint thread, IntPtr layout)
    {
        if (foreground == IntPtr.Zero || thread == 0 || layout == IntPtr.Zero) return "receiver_layout_unknown";
        // A legacy IME layout handle (0xE...) composes every key.
        if (((ulong)layout.ToInt64() & 0xF0000000UL) == 0xE0000000UL) return "input_method_layout";
        foreach (var key in new[] { 0x10, 0x11, 0x12, 0x5B, 0x5C })
            if ((NativeMethods.GetAsyncKeyState(key) & 0x8000) != 0) return "modifier_held";
        if ((TextNative.GetKeyState(0x14) & 0x0001) != 0) return "caps_lock_on";
        var gui = new TextNative.GuiThreadInfo { Size = Marshal.SizeOf<TextNative.GuiThreadInfo>() };
        var focus = TextNative.GetGUIThreadInfo(thread, ref gui) && gui.Focus != IntPtr.Zero ? gui.Focus : foreground;
        var ime = TextNative.ImmGetDefaultIMEWnd(focus);
        if (ime == IntPtr.Zero) return null;
        // IMC_GETOPENSTATUS through the IME window; an unanswered query is
        // treated as open rather than guessed closed.
        if (TextNative.SendMessageTimeout(ime, TextNative.WM_IME_CONTROL, new IntPtr(TextNative.IMC_GETOPENSTATUS), IntPtr.Zero,
                TextNative.SMTO_ABORTIFHUNG, 250, out var open) == IntPtr.Zero) return "input_method_unknown";
        return open != IntPtr.Zero ? "input_method_open" : null;
    }

    private static bool Produces(char character, ushort virtualKey, bool shift, IntPtr layout)
    {
        var state = new byte[256];
        if (shift) { state[ShiftKey] = 0x80; state[0xA0] = 0x80; }
        var buffer = new char[4];
        // Flag 4: do not change the keyboard state (no dead-key residue).
        var count = TextNative.ToUnicodeEx(virtualKey, TextNative.MapVirtualKeyExW(virtualKey, 0, layout), state, buffer, buffer.Length, 4, layout);
        return count == 1 && buffer[0] == character;
    }

    /// One keystroke as a single SendInput batch, so Windows does not
    /// interleave other input and nothing stays pressed afterwards.
    private static void SendLayoutStroke(TextStroke stroke, IntPtr layout)
    {
        var scan = (ushort)TextNative.MapVirtualKeyExW(stroke.VirtualKey, 0, layout);
        var shiftScan = (ushort)TextNative.MapVirtualKeyExW(ShiftKey, 0, layout);
        var inputs = new List<NativeMethods.INPUT>(4);
        if (stroke.Shift) inputs.Add(LayoutInput(ShiftKey, shiftScan, 0));
        inputs.Add(LayoutInput(stroke.VirtualKey, scan, 0));
        inputs.Add(LayoutInput(stroke.VirtualKey, scan, NativeMethods.KEYEVENTF_KEYUP));
        if (stroke.Shift) inputs.Add(LayoutInput(ShiftKey, shiftScan, NativeMethods.KEYEVENTF_KEYUP));
        var batch = inputs.ToArray();
        RequireDesktopAuthority();
        if (SendDesktopInput((uint)batch.Length, batch, Marshal.SizeOf<NativeMethods.INPUT>()) != batch.Length)
        {
            var error = Marshal.GetLastWin32Error();
            // A partially inserted batch must not leave a key or Shift down.
            ReleaseKeyboardInputs(batch.Where(input => (input.union.keyboard.dwFlags & NativeMethods.KEYEVENTF_KEYUP) != 0).ToArray());
            throw new System.ComponentModel.Win32Exception(error);
        }
        // The same per-character pacing as Unicode packets.
        Thread.Sleep(5);
    }

    private static NativeMethods.INPUT LayoutInput(ushort key, ushort scan, uint flags) =>
        new()
        {
            type = NativeMethods.INPUT_KEYBOARD,
            union = new NativeMethods.INPUTUNION
            {
                keyboard = new NativeMethods.KEYBDINPUT { wVk = key, wScan = scan, dwFlags = flags },
            },
        };

    private static class TextNative
    {
        internal const uint WM_IME_CONTROL = 0x0283, SMTO_ABORTIFHUNG = 0x0002;
        internal const int IMC_GETOPENSTATUS = 0x0005;

        [StructLayout(LayoutKind.Sequential)]
        internal struct GuiThreadInfo
        {
            public int Size; public uint Flags;
            public IntPtr Active, Focus, Capture, MenuOwner, MoveSize, Caret;
            public NativeMethods.RECT CaretRect;
        }

        [DllImport("user32.dll")]
        internal static extern IntPtr GetKeyboardLayout(uint thread);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern short VkKeyScanExW(char character, IntPtr layout);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern uint MapVirtualKeyExW(uint code, uint mapType, IntPtr layout);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern int ToUnicodeEx(uint virtualKey, uint scanCode, byte[] keyState,
            [Out] char[] buffer, int bufferLength, uint flags, IntPtr layout);
        [DllImport("user32.dll")]
        internal static extern short GetKeyState(int key);
        [DllImport("user32.dll")]
        internal static extern bool GetGUIThreadInfo(uint thread, ref GuiThreadInfo info);
        [DllImport("imm32.dll")]
        internal static extern IntPtr ImmGetDefaultIMEWnd(IntPtr hwnd);
        [DllImport("user32.dll", SetLastError = true)]
        internal static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam,
            uint flags, uint timeout, out IntPtr result);
    }
}
