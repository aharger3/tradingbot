# deck_ui.py Touch Event Audit

## Event Handler Summary

| Event | Element | Line | Type | Works on Touch? |
|---|---|---|---|---|
| `click` | canvas | 798 | addEventListener | Unreliable; delayed or missing on iPad |
| `onclick` | button#exportJSONL | 148 | inline onclick | Yes (via click) |
| `onclick` | button#copyJSONL | 149 | inline onclick | Yes |
| `onclick` | button#toggleImport | 150 | inline onclick | Yes |
| `onclick` | button#levelsBtn | 151 | inline onclick | Yes |
| `onclick` | button#resetAll | 152 | inline onclick | Yes |
| `onclick` | button.doImport | 159 | inline onclick | Yes |
| `onclick` | button.undoMark | 173 | inline onclick | Yes |
| `onclick` | button.clearTrades | 174 | inline onclick | Yes |
| `onclick` | span.cycleSide | 533 | inline onclick | Yes |
| `onclick` | span.cycleSrc | 534 | inline onclick | Yes |
| `onclick` | span.delTrade | 538 | inline onclick | Yes |
| `change` | input[type=radio] | 791 | addEventListener | Yes |
| `input` | textarea#notes | 794 | addEventListener | Yes |
| `change` | select#reason | 796 | addEventListener | Yes |
| `load` | window | 853 | addEventListener | N/A |
| `resize` | window | 855 | addEventListener | N/A |
| `beforeunload` | window | 861 | addEventListener | N/A |

## Gaps for Touch

### 1. Canvas Click Handler Missing Touch Events
**Line 798** binds only `'click'` event to canvas:
```javascript
canvas.addEventListener('click', function(ev) { onCanvasClick(cid, ev); });
```

**Problem**: On iOS/iPad, canvas `click` events are unreliable:
- Can be delayed by 300ms (browser's tap-to-click debounce)
- May not fire at all in some Safari versions
- Touch events (`touchstart`, `touchend`, `pointerup`) fire immediately

### 2. Modifier Keys (Shift/Alt) Not Accessible on Touch
**Lines 420, 429** use `ev.altKey` and `ev.shiftKey`:
```javascript
if (ev.altKey) { undoMark(cid); return; }
if (ev.shiftKey) { /* stop mark */ }
```

**Problem**: On a phone/tablet, there is no physical Shift or Alt key. Touch cannot combine modifiers.
- Alt+click for undo (line 420) → **impossible on iPhone**
- Shift+click for stop (line 429) → **impossible on iPhone**

### 3. Coordinate Access Assumes Mouse
**Lines 417-418** extract coordinates:
```javascript
var x = (ev.clientX - rect.left) * (canvas.width / rect.width);
var y = (ev.clientY - rect.top) * (canvas.height / rect.height);
```

**Note**: This works for touch events (clientX/clientY exist on touch events), but is incomplete.
- On multi-touch, only the first touch (event.touches[0]) is safe
- If called from touchstart, coordinates are live; from touchend, they're the last position
- No pointer events (pointerdown/pointerup) fallback

### 4. Hit-Testing Assumptions
Functions `idxAtX()` (line 270) and `priceAtY()` (line 268) assume Cartesian (x, y) coordinates:
```javascript
var idxAtX = function(x) { 
  var i = Math.round((x - pad.l - cw / 2) / cw);
  return Math.max(0, Math.min(candles.length - 1, i));
};
var priceAtY = function(y) { 
  return hi - (y - pad.t) / (H - pad.t - pad.b) * range; 
};
```

**Status**: These are **robust**. They do not assume hover, do not use mouse-specific properties, and work correctly with extracted touch coordinates. No change needed here.

---

## Smallest Fix for iPhone Support

**Objective**: Make canvas marking work on touch devices without requiring Shift/Alt modifiers.

### Strategy: Replace `click` with Pointer Events

Change line 798 from:
```javascript
if (canvas) canvas.addEventListener('click', function(ev) { onCanvasClick(cid, ev); });
```

To:
```javascript
if (canvas) {
  canvas.addEventListener('pointerup', function(ev) { onCanvasClick(cid, ev); });
  // Fallback for browsers without pointerup (older Safari):
  canvas.addEventListener('touchend', function(ev) {
    if (ev.touches.length === 0 && ev.changedTouches.length > 0) {
      // Simulate a click-like event from the last touch point
      var t = ev.changedTouches[0];
      var synthetic = {
        clientX: t.clientX,
        clientY: t.clientY,
        altKey: false,
        shiftKey: false
      };
      onCanvasClick(cid, synthetic);
    }
  });
}
```

### Why This Works
1. **`pointerup`** fires for both mouse clicks and touch lifts (no 300ms delay on iPad)
2. **`touchend` fallback** catches older Safari versions (iOS 12 and earlier)
3. **Modifier keys problem unsolved**: Shift/Alt combos remain impossible on touch. Mitigation: Add UI buttons for "Add Stop" and "Undo" instead of keyboard shortcuts.

### Side Effects
- None. `pointerup` is a superset of `click` behavior.
- Existing mouse workflows unchanged.
- Touch now fires immediately, no delay.

---

## Recommendation

**Implement the pointer-events fix** (line 798). This enables canvas marking on iPhone/iPad.

**Then add UI buttons** for stop and undo (instead of relying on Shift/Alt), making them accessible to both touch and mouse users. Consider a floating toolbar near the chart on mobile.
