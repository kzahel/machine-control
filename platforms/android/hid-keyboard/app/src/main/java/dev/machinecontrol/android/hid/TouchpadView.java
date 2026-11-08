package dev.machinecontrol.android.hid;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;

/**
 * In-a-pinch virtual touchpad: one-finger drag moves, tap clicks, two-finger
 * drag scrolls (content follows the fingers), and a two-finger tap right-clicks.
 */
final class TouchpadView extends View {
    private static final float GAIN = 1.6f;
    private static final float SCROLL_STEP = 48f;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int slop;
    private float lastX, lastY, startX, startY, restX, restY, scrollRest;
    private long downTime;
    private int maxPointers;
    private boolean moved;

    TouchpadView(Context context) {
        super(context);
        slop = ViewConfiguration.get(context).getScaledTouchSlop();
        setContentDescription(context.getString(R.string.touchpad));
        paint.setColor(Color.rgb(60, 66, 76));
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(3);
    }

    @Override protected void onDraw(Canvas canvas) {
        canvas.drawColor(Color.rgb(28, 31, 36));
        canvas.drawRoundRect(6, 6, getWidth() - 6, getHeight() - 6, 32, 32, paint);
    }

    private float centroidX(MotionEvent event) {
        float sum = 0;
        for (int i = 0; i < event.getPointerCount(); i++) sum += event.getX(i);
        return sum / event.getPointerCount();
    }

    private float centroidY(MotionEvent event) {
        float sum = 0;
        for (int i = 0; i < event.getPointerCount(); i++) sum += event.getY(i);
        return sum / event.getPointerCount();
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        HidService service = HidService.current;
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downTime = event.getEventTime();
                maxPointers = 1;
                moved = false;
                startX = lastX = event.getX();
                startY = lastY = event.getY();
                restX = restY = scrollRest = 0;
                return true;
            case MotionEvent.ACTION_POINTER_DOWN:
            case MotionEvent.ACTION_POINTER_UP:
                maxPointers = Math.max(maxPointers, event.getPointerCount());
                // Re-anchor so the centroid jump of adding/removing a finger is not motion.
                lastX = centroidX(event);
                lastY = centroidY(event);
                return true;
            case MotionEvent.ACTION_MOVE: {
                float x = centroidX(event), y = centroidY(event);
                float dx = x - lastX, dy = y - lastY;
                lastX = x;
                lastY = y;
                if (Math.hypot(x - startX, y - startY) > slop) moved = true;
                if (service == null) return true;
                if (event.getPointerCount() == 1 && maxPointers == 1) {
                    restX += dx * GAIN;
                    restY += dy * GAIN;
                    int sendX = (int) restX, sendY = (int) restY;
                    restX -= sendX;
                    restY -= sendY;
                    if (sendX != 0 || sendY != 0) service.pointerAsync(() -> service.move(sendX, sendY));
                } else if (event.getPointerCount() >= 2) {
                    // Natural scrolling: fingers up shows content below, a negative wheel.
                    scrollRest += dy;
                    int notches = (int) (scrollRest / SCROLL_STEP);
                    scrollRest -= notches * SCROLL_STEP;
                    if (notches != 0) service.pointerAsync(() -> service.scroll(notches, 0));
                }
                return true;
            }
            case MotionEvent.ACTION_UP:
                if (service != null && !moved && event.getEventTime() - downTime < 300) {
                    int button = maxPointers >= 2 ? Reports.BUTTON_RIGHT : Reports.BUTTON_LEFT;
                    service.pointerAsync(() -> service.click(button, 1, 30));
                    performClick();
                }
                return true;
            default:
                return true;
        }
    }

    @Override public boolean performClick() { return super.performClick(); }
}
