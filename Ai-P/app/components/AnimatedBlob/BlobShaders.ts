export const vertexShader = `
  uniform float uTime;
  uniform float uNoiseScale;
  uniform float uNoiseStrength;
  uniform float uMorphProgress;
  uniform vec3 uDeformation[5];
  uniform float uVoiceActivity[5];
  
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vPosition;
  
  // Simplex noise function (simplified 3D noise)
  vec3 mod289(vec3 x) {
    return x - floor(x * (1.0 / 289.0)) * 289.0;
  }
  
  vec4 mod289(vec4 x) {
    return x - floor(x * (1.0 / 289.0)) * 289.0;
  }
  
  vec4 permute(vec4 x) {
    return mod289(((x*34.0)+1.0)*x);
  }
  
  vec4 taylorInvSqrt(vec4 r) {
    return 1.79284291400159 - 0.85373472095314 * r;
  }
  
  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    
    i = mod289(i);
    vec4 p = permute(permute(permute(
              i.z + vec4(0.0, i1.z, i2.z, 1.0))
            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    
    vec4 x = x_ *ns.x + ns.yyyy;
    vec4 y = y_ *ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x;
    p1 *= norm.y;
    p2 *= norm.z;
    p3 *= norm.w;
    
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }
  
  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    
    vec3 pos = position;
    
    // Multi-layered noise for more organic, fluid deformation
    float noise1 = snoise(pos * uNoiseScale + uTime * 0.15);
    float noise2 = snoise(pos * uNoiseScale * 1.5 + uTime * 0.25);
    float noise3 = snoise(pos * uNoiseScale * 0.5 - uTime * 0.1);
    
    // Combine noise layers for more complex, organic shape
    float combinedNoise = (noise1 * 0.5 + noise2 * 0.3 + noise3 * 0.2);
    
    // Apply deformation with smooth falloff
    pos += normal * combinedNoise * uNoiseStrength;
    
    vPosition = pos;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

export const fragmentShader = `
  uniform float uTime;
  uniform vec3 uColor1;
  uniform vec3 uColor2;
  uniform float uListeningState;
  uniform vec3 uListeningColor;
  uniform float uRippleTime;
  uniform float uGlowIntensity;
  
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vPosition;
  
  void main() {
    // Dynamic gradient with multiple wave layers for fluid color transitions
    float wave1 = sin(uTime * 0.4 + vUv.x * 3.14159) * 0.15;
    float wave2 = cos(uTime * 0.6 + vUv.y * 3.14159) * 0.1;
    float gradientMix = vUv.y + wave1 + wave2;
    gradientMix = clamp(gradientMix, 0.0, 1.0);
    
    vec3 baseColor = mix(uColor1, uColor2, gradientMix);
    
    // Listening state: unified solid color (no gradient)
    // Smooth transition between gradient and unified color
    baseColor = mix(baseColor, uListeningColor, uListeningState);
      
    // Add listening state rings (fade in as uListeningState increases)
    if (uListeningState > 0.0) {
      vec2 center = vec2(0.5, 0.5);
      float dist = length(vUv - center);
      
      // Primary ring
      float ring1 = smoothstep(0.42, 0.45, dist) * smoothstep(0.55, 0.52, dist);
      float pulse1 = 0.6 + 0.4 * sin(uRippleTime * 4.0);
      
      // Secondary ring (slightly offset)
      float ring2 = smoothstep(0.38, 0.40, dist) * smoothstep(0.60, 0.58, dist);
      float pulse2 = 0.5 + 0.3 * sin(uRippleTime * 4.0 + 1.5);
      
      // Combine rings with pulsing effect
      float combinedRing = max(ring1 * pulse1, ring2 * pulse2);
      vec3 ringColor = uListeningColor * combinedRing;
      baseColor = mix(baseColor, ringColor, combinedRing * 0.9 * uListeningState);
      
      // Add subtle inner glow (fade in with listening state)
      float innerGlow = smoothstep(0.5, 0.3, dist);
      baseColor += uListeningColor * innerGlow * 0.2 * uListeningState;
    }
    
    // Enhanced fresnel effect for premium edge glow
    float fresnel = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.5);
    vec3 glowColor;
    
    // Smooth transition between gradient glow and unified color glow
    vec3 gradientGlow = mix(uColor1, uColor2, 0.5);
    float shimmer = sin(uTime * 2.0 + vUv.x * 10.0) * 0.05;
    gradientGlow += vec3(shimmer);
    glowColor = mix(gradientGlow, uListeningColor, uListeningState);
    
    vec3 finalColor = mix(baseColor, glowColor, fresnel * 0.4 * uGlowIntensity);
    
    // Subtle vignette for depth
    float vignette = 1.0 - smoothstep(0.3, 0.8, length(vUv - 0.5));
    finalColor *= 0.7 + 0.3 * vignette;
    
    gl_FragColor = vec4(finalColor, 0.98);
  }
`;
