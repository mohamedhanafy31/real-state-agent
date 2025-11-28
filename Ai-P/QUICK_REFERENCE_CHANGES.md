# Quick Reference: Exact Code Changes

## File: `app/components/AnimatedBlob/BlobShaders.ts`

### Change 1: Base Colors (Lines 31-32)
```glsl
// OLD:
vec3 colorBlue = vec3(0.25, 0.65, 1.0);    // Brighter blue
vec3 colorCyan = vec3(0.1, 0.85, 1.0);     // Brighter cyan

// NEW:
vec3 colorBlue = vec3(0.3, 0.7, 1.0);      // More luminous blue
vec3 colorCyan = vec3(0.15, 0.9, 1.0);     // More luminous cyan
```

---

### Change 2: Silent State Brightening (Line 126)
```glsl
// OLD:
ringColor += vec3(0.15, 0.2, 0.25); // More brightening

// NEW:
ringColor += vec3(0.2, 0.25, 0.3); // Enhanced brightening
```

---

### Change 3: Listening State Brightening (Line 132)
```glsl
// OLD:
ringColor += vec3(0.15, 0.2, 0.25); // Brighten

// NEW:
ringColor += vec3(0.2, 0.25, 0.3); // Enhanced brightening
```

---

### Change 4: Glow Spread (Line 90)
```glsl
// OLD:
float glow = 1.0 - smoothstep(width, width * 5.0, distFromRing);  // Moderate glow

// NEW:
float glow = 1.0 - smoothstep(width, width * 6.5, distFromRing);  // Wider atmospheric glow
```

---

### Change 5: Ring Thickness (Line 111)
```glsl
// OLD:
float ringWidth = 0.022;  // Thicker rings

// NEW:
float ringWidth = 0.025;  // More prominent rings
```

---

### Change 6: Ring Visibility (Line 160)
```glsl
// OLD:
vec3 ringFinal = ringColor * ringAlpha * 1.4;  // More visible

// NEW:
vec3 ringFinal = ringColor * ringAlpha * 1.5;  // Enhanced visibility
```

---

### Change 7: Outer Glow (Line 196)
```glsl
// OLD:
finalColor += finalColor * outerGlow * 0.2 * circularMask;  // Constrained to circle

// NEW:
finalColor += finalColor * outerGlow * 0.25 * circularMask;  // Enhanced ambient glow
```

---

## Summary Table

| Line | Change | Old Value | New Value |
|------|--------|-----------|-----------|
| 31 | colorBlue | `vec3(0.25, 0.65, 1.0)` | `vec3(0.3, 0.7, 1.0)` |
| 32 | colorCyan | `vec3(0.1, 0.85, 1.0)` | `vec3(0.15, 0.9, 1.0)` |
| 126 | Silent brightening | `vec3(0.15, 0.2, 0.25)` | `vec3(0.2, 0.25, 0.3)` |
| 132 | Listening brightening | `vec3(0.15, 0.2, 0.25)` | `vec3(0.2, 0.25, 0.3)` |
| 90 | Glow spread | `width * 5.0` | `width * 6.5` |
| 111 | Ring width | `0.022` | `0.025` |
| 160 | Ring visibility | `1.4` | `1.5` |
| 196 | Outer glow | `0.2` | `0.25` |

---

## Implementation Order

1. **Colors** (Changes 1, 2, 3) - Most visible
2. **Glow** (Changes 4, 7) - Atmospheric effect
3. **Rings** (Changes 5, 6) - Visibility

---

**Total Changes**: 8 modifications in 1 file  
**Estimated Time**: 10-15 minutes  
**Risk**: Low (visual only)

