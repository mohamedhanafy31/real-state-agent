'use client';

import { useCallback, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useAppStore } from '@/store/useAppStore';
import type { BlobState } from '@/types';
import { vertexShader, fragmentShader } from './BlobShaders';
import styles from './BlobCanvas.module.css';

type SplitPiece = THREE.Mesh<THREE.SphereGeometry, THREE.MeshStandardMaterial> & {
    materialRef: THREE.MeshStandardMaterial;
    startColor: THREE.Color;
    targetColor: THREE.Color;
};

export default function BlobCanvas() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const sceneRef = useRef<THREE.Scene | null>(null);
    const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
    const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
    const blobMeshRef = useRef<THREE.Mesh | null>(null);
    const materialRef = useRef<THREE.ShaderMaterial | null>(null);
    const animationIdRef = useRef<number | null>(null);
    const circlesRef = useRef<THREE.Mesh[]>([]);
    const thinkingStartTimeRef = useRef<number | null>(null);
    const isTransitioningRef = useRef<boolean>(false);
    const mainClockRef = useRef<THREE.Clock | null>(null);
    const splitPiecesRef = useRef<SplitPiece[]>([]);
    const isSplittingRef = useRef<boolean>(false);
    const isDisposedRef = useRef<boolean>(false); // Track if resources are disposed
    const webglErrorCountRef = useRef<number>(0); // Track consecutive WebGL errors for recovery

    const { blob, content } = useAppStore();
    const blobStateRef = useRef<BlobState>(blob.state);
    const frequencyRef = useRef<number[]>(blob.frequencyData);

    // Get blob size based on device and images
    const getBlobSize = useCallback(() => {
        const hasImages = content.gallery.length > 0;
        if (typeof window === 'undefined') return 450;

        const width = window.innerWidth;
        if (width < 768) {
            return hasImages ? 110 : 280;
        } else if (width < 1024) {
            return hasImages ? 170 : 350;
        } else {
            return 450;
        }
    }, [content.gallery.length]);

    useEffect(() => {
        // Reset disposed flag when component (re)mounts
        isDisposedRef.current = false;

        if (!canvasRef.current) return;

        const canvas = canvasRef.current;
        const size = getBlobSize();

        // Scene setup
        const scene = new THREE.Scene();
        sceneRef.current = scene;

        // Camera setup
        const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
        camera.position.z = 5;
        cameraRef.current = camera;

        // Renderer setup
        const renderer = new THREE.WebGLRenderer({
            canvas,
            alpha: true,
            antialias: true,
        });
        renderer.setSize(size, size);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        rendererRef.current = renderer;

        // Shader material
        const material = new THREE.ShaderMaterial({
            vertexShader,
            fragmentShader,
            uniforms: {
                uTime: { value: 0 },
                uNoiseScale: { value: 0.8 },
                uNoiseStrength: { value: 0.15 },
                uColor1: { value: new THREE.Color(0x9333EA) }, // Purple
                uColor2: { value: new THREE.Color(0xD4AF37) }, // Gold
                uListeningState: { value: 0.0 },
                uListeningColor: { value: new THREE.Color(0x672793) }, // Unified purple color #672793
                uRippleTime: { value: 0 },
                uGlowIntensity: { value: 1.0 },
                uMorphProgress: { value: 0 },
                uDeformation: {
                    value: [
                        new THREE.Vector3(),
                        new THREE.Vector3(),
                        new THREE.Vector3(),
                        new THREE.Vector3(),
                        new THREE.Vector3(),
                    ]
                },
                uVoiceActivity: { value: [0, 0, 0, 0, 0] },
            },
            transparent: true,
        });
        materialRef.current = material;

        // Create blob geometry (icosahedron for smooth sphere)
        // Use smooth sphere geometry to allow perfect circular listening state
        const geometry = new THREE.SphereGeometry(1.5, 96, 96);
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);
        blobMeshRef.current = mesh;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0xffffff, 0.8);
        pointLight.position.set(2, 2, 2);
        scene.add(pointLight);

        // Animation loop
        const clock = new THREE.Clock(true); // Start clock immediately
        mainClockRef.current = clock; // Store clock reference for transitions

        const animate = () => {
            // Guard: Exit immediately if disposed
            if (isDisposedRef.current) {
                return;
            }

            // Guard: Exit if resources have been disposed (component unmounted)
            if (!material || !mesh || !renderer || !camera || !scene) {
                return;
            }

            // Additional guard: Check if Three.js objects are still valid
            try {
                if (material.uniforms === undefined) {
                    return;
                }
            } catch {
                return;
            }

            // Get current state from store directly (not from closure) to avoid stale values
            const currentStoreState = useAppStore.getState().blob.state;
            const elapsedTime = clock.getElapsedTime();

            // THINKING state: camera adjustment only (animation handled in separate useEffect)
            if (currentStoreState === 'thinking') {
                // Adjust camera to fit all 6 blobs with reduced spacing
                // Use orthographic-like perspective to prevent oval distortion on edges
                const targetFOV = 50; // Narrower FOV to reduce perspective distortion
                camera.fov = THREE.MathUtils.lerp(camera.fov, targetFOV, 0.1);
                // Move camera back to fit all pieces while maintaining circle shape
                const targetZ = 8; // Move camera further back
                camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.1);
                camera.updateProjectionMatrix();
            }

            // Defensive WebGL operations - wrap in try-catch to handle mid-frame resource changes
            try {
                if (!material || !material.uniforms || isDisposedRef.current) {
                    return;
                }

                material.uniforms.uTime.value = elapsedTime;
                material.uniforms.uRippleTime.value = elapsedTime;

                // Target values for interpolation
                let targetScale = 1.0;
                let targetNoiseStrength = 0.15;
                let targetListeningState = 0.0;

                // SILENT state: fluid breathing animation with organic pulsing
                if (currentStoreState === 'silent') {
                    // Multi-frequency breathing for more natural feel
                    const breath1 = Math.sin(elapsedTime * 0.8) * 0.04;
                    const breath2 = Math.sin(elapsedTime * 1.2 + 1.0) * 0.02;
                    targetScale = 0.96 + breath1 + breath2;
                    // Slightly more dynamic noise for organic feel
                    targetNoiseStrength = 0.18 + Math.sin(elapsedTime * 0.3) * 0.03;
                    targetListeningState = 0.0;
                }

                // LISTENING state: perfect circle with subtle breathing and rings
                else if (currentStoreState === 'listening') {
                    // Subtle breathing while maintaining perfect circle
                    targetScale = 0.99 + Math.sin(elapsedTime * 2.5) * 0.01;
                    targetNoiseStrength = 0.0; // No deformation (perfect circle)
                    targetListeningState = 1.0;
                }

                // SPEAKING state: responds to voice activity with base animation
                else if (currentStoreState === 'speaking') {
                    const frequencies = frequencyRef.current;

                    // Base breathing animation (same as silent for consistency)
                    const breath1 = Math.sin(elapsedTime * 0.8) * 0.04;
                    const breath2 = Math.sin(elapsedTime * 1.2 + 1.0) * 0.02;
                    const baseScale = 0.96;
                    const baseNoise = 0.18;
                    const baseNoiseVariation = Math.sin(elapsedTime * 0.3) * 0.03;

                    if (frequencies && frequencies.length > 0) {
                        // Calculate average activity from frequency data
                        const avgActivity = frequencies.reduce((sum, val) => sum + (val || 0), 0) / frequencies.length;
                        const maxActivity = Math.max(...frequencies.map(f => f || 0));

                        // Apply voice activity to scale (adds to base breathing)
                        // Scale variation: up to 30% based on average activity (increased for bigger effect)
                        const audioScaleVariation = avgActivity * 0.30;
                        targetScale = baseScale + breath1 + breath2 + audioScaleVariation;

                        // Apply voice activity to noise strength (adds to base variation)
                        // Noise variation: up to 0.35 additional based on max activity (increased for bigger effect)
                        // Range: 0.18-0.21 (base) + 0-0.35 (audio) = 0.18-0.56
                        const audioNoiseVariation = maxActivity * 0.35;
                        targetNoiseStrength = baseNoise + baseNoiseVariation + audioNoiseVariation;

                        targetListeningState = 0.0;
                    } else {
                        // No frequency data - use base animation only (same as silent)
                        targetScale = baseScale + breath1 + breath2;
                        targetNoiseStrength = baseNoise + baseNoiseVariation;
                        targetListeningState = 0.0;
                    }
                }

                // Reset camera FOV and position for non-thinking states
                if (currentStoreState !== 'thinking') {
                    const defaultFOV = 50;
                    const defaultZ = 5; // Default camera Z position
                    camera.fov = THREE.MathUtils.lerp(camera.fov, defaultFOV, 0.1);
                    camera.position.z = THREE.MathUtils.lerp(camera.position.z, defaultZ, 0.1);
                    camera.updateProjectionMatrix();
                }

                // Apply smooth transitions to main blob
                // Don't override transition values if a transition is in progress
                if (mesh && !isTransitioningRef.current) {
                    mesh.scale.setScalar(THREE.MathUtils.lerp(mesh.scale.x, targetScale, 0.12));

                    if (currentStoreState === 'listening') {
                        mesh.rotation.set(0, 0, 0);
                    } else {
                        // Slow, smooth rotation with subtle X-axis movement for organic feel
                        mesh.rotation.y += 0.003;
                        mesh.rotation.x = Math.sin(elapsedTime * 0.2) * 0.05;
                    }

                    // Use faster lerp for listening state to ensure it reaches target quickly
                    const lerpFactor = currentStoreState === 'listening' ? 0.3 : 0.1;
                    material.uniforms.uListeningState.value = THREE.MathUtils.lerp(
                        material.uniforms.uListeningState.value,
                        targetListeningState,
                        lerpFactor
                    );
                    material.uniforms.uNoiseStrength.value = THREE.MathUtils.lerp(
                        material.uniforms.uNoiseStrength.value,
                        targetNoiseStrength,
                        0.1
                    );
                }
            } catch (error) {
                // Track consecutive errors for recovery
                webglErrorCountRef.current++;

                if (isDisposedRef.current) {
                    return;
                }

                // Log warning if multiple consecutive errors (possible resource corruption)
                if (webglErrorCountRef.current >= 3) {
                    console.warn(`WebGL uniform errors detected (${webglErrorCountRef.current} consecutive). Resources may need recreation.`, error);
                }
                return;
            }
            // Reset error counter on successful uniform updates
            webglErrorCountRef.current = 0;


            // Don't render during transitions - transition animation handles rendering
            if (!isTransitioningRef.current && !isSplittingRef.current) {
                try {
                    // Defensive render - catch errors when renderer/scene/camera become invalid
                    if (!renderer || !scene || !camera || isDisposedRef.current) {
                        return;
                    }
                    renderer.render(scene, camera);
                    // Reset error counter on successful render
                    webglErrorCountRef.current = 0;
                } catch (error) {
                    // Track consecutive errors
                    webglErrorCountRef.current++;

                    if (isDisposedRef.current) {
                        return;
                    }

                    // Log warning if multiple consecutive errors
                    if (webglErrorCountRef.current >= 3) {
                        console.warn(`WebGL render errors detected (${webglErrorCountRef.current} consecutive). Animation may be degraded.`, error);
                    }
                    return;
                }
            }
            animationIdRef.current = requestAnimationFrame(animate);
        };

        animate();

        // Handle resize
        const handleResize = () => {
            const newSize = getBlobSize();
            // Adjust canvas size based on current state
            if (blobStateRef.current === 'thinking') {
                const targetWidth = newSize * 1.8;
                renderer.setSize(targetWidth, newSize);
                camera.aspect = targetWidth / newSize;
            } else {
                renderer.setSize(newSize, newSize);
                camera.aspect = 1;
            }
            camera.updateProjectionMatrix();
        };

        window.addEventListener('resize', handleResize);

        // Cleanup
        return () => {
            // Set disposed flag first to stop all animations immediately
            isDisposedRef.current = true;

            window.removeEventListener('resize', handleResize);
            if (animationIdRef.current) {
                cancelAnimationFrame(animationIdRef.current);
            }
            geometry.dispose();
            material.dispose();
            renderer.dispose();
        };
    }, [getBlobSize]);

    // Handle state transitions
    useEffect(() => {
        if (!sceneRef.current || !blobMeshRef.current) return;

        const scene = sceneRef.current;
        const mainBlob = blobMeshRef.current;

        // Get current state from store to avoid stale values
        const currentState = useAppStore.getState().blob.state;

        // SILENT and LISTENING states: use main blob (transform properties only)
        if (currentState === 'silent' || currentState === 'listening') {
            mainBlob.visible = true;

            // Clean up any circles from previous states
            circlesRef.current.forEach(circle => scene.remove(circle));
            circlesRef.current = [];

            // Clean up split pieces when leaving thinking state
            splitPiecesRef.current.forEach(piece => scene.remove(piece));
            splitPiecesRef.current = [];
        }
        // THINKING state: hide main blob, keep split pieces visible
        else if (currentState === 'thinking') {
            mainBlob.visible = false;

            // Reset thinking start time when entering thinking mode
            // This will be set in the animation loop using performance.now()
            if (blobStateRef.current !== 'thinking') {
                thinkingStartTimeRef.current = null; // Reset to trigger initialization in animation loop
            }

            // Clear any existing circles (shouldn't be any, but just in case)
            circlesRef.current.forEach(circle => scene.remove(circle));
            circlesRef.current = [];

            // DO NOT remove split pieces here - they should already be visible from the split animation
            // They will be animated by the thinking animation loop
            // Only remove them if we're NOT in a split transition (to avoid race conditions)
            if (!isSplittingRef.current && splitPiecesRef.current.length === 0) {
                // Thinking state but no split pieces found - this might be a race condition
            }
        }
        // SPEAKING state: use main blob (merged from thinking state)
        else if (currentState === 'speaking') {
            // Ensure main blob is visible (should be after merge animation)
            if (blobMeshRef.current) {
                blobMeshRef.current.visible = true;
            }

            // Clean up any circles (not used in speaking mode anymore)
            circlesRef.current.forEach(circle => scene.remove(circle));
            circlesRef.current = [];

            // Clean up any remaining split pieces (should be cleaned up by merge animation, but just in case)
            splitPiecesRef.current.forEach(piece => scene.remove(piece));
            splitPiecesRef.current = [];
        }
        // Default: show main blob
        else {
            mainBlob.visible = true;

            // Clean up circles
            circlesRef.current.forEach(circle => scene.remove(circle));
            circlesRef.current = [];
        }
    }, [blob.state]);

    useEffect(() => {
        // Get current state from store to ensure we have the latest value
        const storeState = useAppStore.getState().blob.state;
        const prevState = blobStateRef.current;
        const newState = storeState; // Use store state instead of potentially stale blob.state

        if (prevState !== newState) {
            // State changed
        }

        blobStateRef.current = newState;

        // Track when thinking mode starts
        if (newState === 'thinking' && prevState !== 'thinking') {
            // We'll use the clock's elapsed time, so we need to track it in the animation loop
            // For now, set a flag that will be used in the animation loop
            thinkingStartTimeRef.current = 0; // Will be set in animation loop
        }

        // Immediately resize canvas when state changes
        if (rendererRef.current && cameraRef.current) {
            const baseSize = getBlobSize();
            if (newState === 'thinking') {
                const targetWidth = baseSize * 1.8;
                rendererRef.current.setSize(targetWidth, baseSize);
                cameraRef.current.aspect = targetWidth / baseSize;
                cameraRef.current.updateProjectionMatrix();
            } else {
                rendererRef.current.setSize(baseSize, baseSize);
                cameraRef.current.aspect = 1;
                cameraRef.current.updateProjectionMatrix();
            }
        }
    }, [blob.state, getBlobSize]); // Keep dependency on blob.state to trigger re-render when store updates

    useEffect(() => {
        frequencyRef.current = blob.frequencyData;
    }, [blob.frequencyData]);

    // Update frequency data for speaking state
    useEffect(() => {
        if (blob.state === 'speaking' && materialRef.current) {
            materialRef.current.uniforms.uVoiceActivity.value = blob.frequencyData;
        }
    }, [blob.frequencyData, blob.state]);

    const prevStateRef = useRef<BlobState>('silent');
    const transitionFrameRef = useRef<number | null>(null);

    useEffect(() => {
        return () => {
            if (transitionFrameRef.current) {
                cancelAnimationFrame(transitionFrameRef.current);
            }
        };
    }, []);

    useEffect(() => {
        if (!materialRef.current || !blobMeshRef.current) {
            prevStateRef.current = blob.state;
            return;
        }

        const prevState = prevStateRef.current;
        const currentState = blob.state;

        // SILENT ↔ LISTENING transition: Transform the same blob (no new meshes created)
        // SILENT: Irregular blob with gradient colors (purple to gold) + noise deformation
        // LISTENING: Perfect circle with unified color (#672793) + no noise
        const isListeningTransition =
            (prevState === 'silent' && currentState === 'listening') ||
            (prevState === 'listening' && currentState === 'silent');

        // LISTENING → THINKING transition: Split blob into 6 pieces
        const isSplitTransition = prevState === 'listening' && currentState === 'thinking';

        // THINKING → SPEAKING transition: Merge 6 pieces back into one blob
        const isMergeTransition = prevState === 'thinking' && currentState === 'speaking';

        // Reset transition flag if not in a listening, split, or merge transition
        if (!isListeningTransition && !isSplitTransition && !isMergeTransition) {
            isTransitioningRef.current = false;
            isSplittingRef.current = false;
        }

        if (isListeningTransition) {
            if (transitionFrameRef.current) {
                cancelAnimationFrame(transitionFrameRef.current);
                transitionFrameRef.current = null;
            }

            const material = materialRef.current;
            const mesh = blobMeshRef.current;
            const renderer = rendererRef.current;
            const scene = sceneRef.current;
            const camera = cameraRef.current;

            if (!material || !mesh || !renderer || !scene || !camera) {
                prevStateRef.current = currentState;
                return;
            }

            // Smooth morph transition over 1 second - transforms properties only
            const duration = 1000;
            const startTime = performance.now();
            isTransitioningRef.current = true;

            // Helper function for timestamped logging (disabled for silent/listening transitions)
            const logWithTime = (..._args: unknown[]) => undefined;

            // Transform properties:
            // 1. Color: gradient (0) → unified color (1) via uListeningState
            const startListening = material.uniforms.uListeningState.value;
            const targetListening = currentState === 'listening' ? 1 : 0;

            // 2. Shape: irregular/noise (0.15) → perfect circle (0) via uNoiseStrength
            const startNoise = material.uniforms.uNoiseStrength.value;
            const targetNoise = currentState === 'listening' ? 0 : 0.15;

            // 3. Scale: breathing animation smoothly stops
            // SILENT base: 0.96, LISTENING base: 0.99 (but we use 1.0 for stable transition)
            const startScale = mesh.scale.x;
            const targetScale = currentState === 'listening' ? 1.0 : 0.96;

            // 4. Rotation: stop rotation in listening mode, resume in silent mode
            const startRotationY = mesh.rotation.y;
            const startRotationX = mesh.rotation.x;
            const targetRotationY = currentState === 'listening' ? 0 : startRotationY;
            const targetRotationX = currentState === 'listening' ? 0 : startRotationX;

            // Log initial state
            logWithTime(`Starting ${prevState} → ${currentState} transition`);
            logWithTime('Initial state values:', {
                listeningState: startListening.toFixed(3),
                noiseStrength: startNoise.toFixed(3),
                scale: startScale.toFixed(3),
                rotationY: startRotationY.toFixed(3),
                rotationX: startRotationX.toFixed(3)
            });
            logWithTime('Target state values:', {
                listeningState: targetListening,
                noiseStrength: targetNoise,
                scale: targetScale,
                rotationY: targetRotationY,
                rotationX: targetRotationX
            });

            // Use the main clock for continuous time updates during transition
            const getElapsedTime = () => {
                return mainClockRef.current ? mainClockRef.current.getElapsedTime() : performance.now() / 1000;
            };

            // Track last logged progress to log at milestones
            let lastLoggedProgress = -1;
            let lastRenderLogTime = 0;
            const logMilestones = [0, 0.25, 0.5, 0.75, 1.0];

            const animateTransition = (time: number) => {
                const elapsed = getElapsedTime();
                const progress = Math.min((time - startTime) / duration, 1);
                // Smooth easing function for natural transition
                const eased = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 3) / 2;

                // Update time uniforms to keep shader animations running
                material.uniforms.uTime.value = elapsed;
                material.uniforms.uRippleTime.value = elapsed;

                // Update color transition (gradient ↔ unified)
                const newListeningState = THREE.MathUtils.lerp(
                    startListening,
                    targetListening,
                    eased
                );
                material.uniforms.uListeningState.value = newListeningState;

                // Update shape transition (irregular ↔ perfect circle)
                const newNoiseStrength = THREE.MathUtils.lerp(
                    startNoise,
                    targetNoise,
                    eased
                );
                material.uniforms.uNoiseStrength.value = newNoiseStrength;

                // Update scale transition (breathing stops smoothly)
                const newScale = THREE.MathUtils.lerp(startScale, targetScale, eased);
                mesh.scale.setScalar(newScale);

                // Update rotation transition (rotation stops/resumes smoothly)
                const newRotationY = THREE.MathUtils.lerp(startRotationY, targetRotationY, eased);
                const newRotationX = THREE.MathUtils.lerp(startRotationX, targetRotationX, eased);
                mesh.rotation.y = newRotationY;
                mesh.rotation.x = newRotationX;

                // Log at milestones (0%, 25%, 50%, 75%, 100%)
                const currentMilestone = logMilestones.find(m => progress >= m && lastLoggedProgress < m);
                if (currentMilestone !== undefined) {
                    const milestonePercent = (currentMilestone * 100).toFixed(0);
                    logWithTime(`Progress ${milestonePercent}% - Transformation values:`, {
                        progress: (progress * 100).toFixed(1) + '%',
                        eased: eased.toFixed(3),
                        listeningState: newListeningState.toFixed(3),
                        noiseStrength: newNoiseStrength.toFixed(3),
                        scale: newScale.toFixed(3),
                        rotationY: newRotationY.toFixed(3),
                        rotationX: newRotationX.toFixed(3)
                    });
                    lastLoggedProgress = currentMilestone;
                }

                // Render the scene during transition (transition takes priority)
                if (renderer && scene && camera) {
                    renderer.render(scene, camera);
                    // Log render every 200ms to verify rendering is happening
                    const renderTime = performance.now();
                    if (!lastRenderLogTime || renderTime - lastRenderLogTime > 200) {
                        logWithTime(`✓ Rendering frame - Progress: ${(progress * 100).toFixed(1)}%`, {
                            listeningState: newListeningState.toFixed(3),
                            noiseStrength: newNoiseStrength.toFixed(3),
                            scale: newScale.toFixed(3)
                        });
                        lastRenderLogTime = renderTime;
                    }
                } else {
                    logWithTime('✗ ERROR: Cannot render - missing renderer/scene/camera');
                }

                if (progress < 1) {
                    transitionFrameRef.current = requestAnimationFrame(animateTransition);
                } else {
                    // Transition complete
                    logWithTime(`Completed ${prevState} → ${currentState} transition`);
                    logWithTime('Final state values:', {
                        listeningState: material.uniforms.uListeningState.value.toFixed(3),
                        noiseStrength: material.uniforms.uNoiseStrength.value.toFixed(3),
                        scale: mesh.scale.x.toFixed(3),
                        rotationY: mesh.rotation.y.toFixed(3),
                        rotationX: mesh.rotation.x.toFixed(3)
                    });

                    isTransitioningRef.current = false;
                    transitionFrameRef.current = null;
                    // Ensure final values are set
                    if (currentState === 'listening') {
                        material.uniforms.uNoiseStrength.value = 0;
                        material.uniforms.uListeningState.value = 1;
                        mesh.rotation.set(0, 0, 0);
                        mesh.scale.setScalar(1);
                    } else if (currentState === 'silent') {
                        // Reset to silent state values (will be animated by main loop)
                        material.uniforms.uListeningState.value = 0;
                        // Noise strength will be set by main loop based on state
                    }
                    // Final render to ensure state is correct
                    if (renderer && scene && camera) {
                        renderer.render(scene, camera);
                    }
                }
            };

            transitionFrameRef.current = requestAnimationFrame(animateTransition);
        } else if (currentState === 'listening' && !isTransitioningRef.current && materialRef.current && blobMeshRef.current) {
            // Ensure circle if state entered through other transitions (e.g., degraded connection)
            // Only set if not currently transitioning
            materialRef.current.uniforms.uNoiseStrength.value = 0;
            materialRef.current.uniforms.uListeningState.value = 1;
            blobMeshRef.current.rotation.set(0, 0, 0);
            blobMeshRef.current.scale.setScalar(1);
        }
        // LISTENING → THINKING: Split animation - transform the blob into 4 pieces
        else if (isSplitTransition) {
            if (transitionFrameRef.current) {
                cancelAnimationFrame(transitionFrameRef.current);
                transitionFrameRef.current = null;
            }

            const material = materialRef.current;
            const mainBlob = blobMeshRef.current;
            const renderer = rendererRef.current;
            const scene = sceneRef.current;
            const camera = cameraRef.current;

            if (!material || !mainBlob || !renderer || !scene || !camera) {
                prevStateRef.current = currentState;
                return;
            }

            // Clean up any existing split pieces
            splitPiecesRef.current.forEach(piece => scene.remove(piece));
            splitPiecesRef.current = [];

            // Clean up any existing circles
            circlesRef.current.forEach(circle => scene.remove(circle));
            circlesRef.current = [];

            // Create 6 blob pieces that start overlapping at center (looks like one blob)
            const circleSize = 0.3; // Smaller blobs
            const spacing = 1.8; // Reduced spacing between pieces
            const targetPositions: THREE.Vector3[] = [];

            // Calculate positions for 6 pieces centered around origin
            for (let i = 0; i < 6; i++) {
                const targetX = (i - 2.5) * spacing; // -4.5, -2.7, -0.9, 0.9, 2.7, 4.5
                targetPositions.push(new THREE.Vector3(targetX, 0, 0));
            }

            // Store initial main blob scale for animation
            const initialMainScale = mainBlob.scale.x;

            // Starting color (purple from listening state)
            const startColor = new THREE.Color(0x672793);
            // Target color (black)
            const targetColor = new THREE.Color(0x000000);

            for (let i = 0; i < 6; i++) {
                // Use a perfect sphere geometry to ensure perfect circles (not ovals)
                const pieceGeometry = new THREE.SphereGeometry(circleSize, 32, 32);
                // Start with purple color (will animate to black)
                const pieceMaterial = new THREE.MeshStandardMaterial({
                    color: startColor.clone(), // Start with purple
                    emissive: startColor.clone(),
                    emissiveIntensity: 0.3,
                    metalness: 0.0,
                    roughness: 0.5,
                });

                const piece = new THREE.Mesh(pieceGeometry, pieceMaterial) as SplitPiece;

                // Start at exact same position as main blob (overlapping perfectly)
                piece.position.copy(mainBlob.position);
                piece.rotation.copy(mainBlob.rotation);
                // Use uniform scale to maintain perfect circle shape
                piece.scale.set(1, 1, 1);

                // Store material reference for color animation
                piece.materialRef = pieceMaterial;
                piece.startColor = startColor.clone();
                piece.targetColor = targetColor.clone();

                // Initially they're all at the same position, so they look like one blob
                scene.add(piece);
                splitPiecesRef.current.push(piece);
            }

            // Store initial main blob position (initialMainScale already defined above)
            const initialMainPosition = mainBlob.position.clone();

            isSplittingRef.current = true;
            isTransitioningRef.current = true;

            const duration = 1000; // 1 second
            const startTime = performance.now();

            const animateSplit = (time: number) => {
                const progress = Math.min((time - startTime) / duration, 1);
                // Smooth easing
                const eased = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 3) / 2;

                splitPiecesRef.current.forEach((piece, i) => {
                    const startPos = initialMainPosition.clone();
                    const targetPos = targetPositions[i];

                    // Animate position: move from center to target position
                    piece.position.lerpVectors(startPos, targetPos, eased);

                    // Animate color: transition from purple to black
                    if (piece.materialRef && piece.startColor && piece.targetColor) {
                        // Interpolate color smoothly
                        piece.materialRef.color.lerpColors(piece.startColor, piece.targetColor, eased);
                        piece.materialRef.emissive.lerpColors(piece.startColor, piece.targetColor, eased);
                    }

                    // Pieces maintain uniform scale to keep perfect circle shape
                    // Keep the scale constant during animation (already set to 1,1,1)
                    piece.scale.set(1, 1, 1);
                });

                // Animate main blob: shrink slightly (not to 0) and fade out
                const mainBlobScale = THREE.MathUtils.lerp(initialMainScale, initialMainScale * 0.3, eased);
                mainBlob.scale.setScalar(mainBlobScale);

                // Fade out main blob as pieces separate
                if (material.uniforms && material.uniforms.uGlowIntensity) {
                    material.uniforms.uGlowIntensity.value = THREE.MathUtils.lerp(1.0, 0, eased);
                }

                // Render with error handling to suppress WebGL warnings
                try {
                    renderer.render(scene, camera);
                } catch (error) {
                    // Suppress WebGL errors during animation transitions
                    // These are typically harmless warnings about shader programs
                }

                if (progress < 1) {
                    transitionFrameRef.current = requestAnimationFrame(animateSplit);
                } else {
                    // Animation complete - hide main blob and KEEP split pieces visible
                    // Hide main blob after animation (keep it at shrunk size, not 0)
                    mainBlob.visible = false;
                    mainBlob.scale.setScalar(initialMainScale * 0.3);

                    // KEEP split pieces - they will stay visible in thinking mode
                    // DO NOT remove them - they need to be animated by the thinking animation loop
                    // Verify pieces are still in the scene
                    splitPiecesRef.current.forEach((piece) => {
                        if (!scene.getObjectById(piece.id)) {
                            // Piece not found in scene after animation
                        }
                    });

                    // Clear any existing circles (shouldn't be any, but just in case)
                    circlesRef.current.forEach(circle => scene.remove(circle));
                    circlesRef.current = [];

                    // Reset main blob scale for future use
                    mainBlob.scale.setScalar(1.0);
                    if (material.uniforms && material.uniforms.uGlowIntensity) {
                        material.uniforms.uGlowIntensity.value = 1.0;
                    }

                    isSplittingRef.current = false;
                    isTransitioningRef.current = false;
                    transitionFrameRef.current = null;

                    // Final render with error handling
                    try {
                        renderer.render(scene, camera);
                    } catch (error) {
                        // Suppress WebGL errors during animation transitions
                    }
                }
            };

            transitionFrameRef.current = requestAnimationFrame(animateSplit);
        }
        // THINKING → SPEAKING: Merge animation - unify 6 pieces back into one blob
        else if (isMergeTransition) {
            if (transitionFrameRef.current) {
                cancelAnimationFrame(transitionFrameRef.current);
                transitionFrameRef.current = null;
            }

            const material = materialRef.current;
            const mainBlob = blobMeshRef.current;
            const renderer = rendererRef.current;
            const scene = sceneRef.current;
            const camera = cameraRef.current;

            if (!material || !mainBlob || !renderer || !scene || !camera) {
                prevStateRef.current = currentState;
                return;
            }

            const pieces = splitPiecesRef.current;
            if (pieces.length === 0) {
                // No pieces to merge, just restore main blob
                mainBlob.visible = true;
                mainBlob.scale.setScalar(1.0);
                if (material.uniforms) {
                    material.uniforms.uGlowIntensity.value = 1.0;
                    material.uniforms.uListeningState.value = 0.0; // Silent mode style
                    material.uniforms.uNoiseStrength.value = 0.18; // Silent mode noise
                }
                prevStateRef.current = currentState;
                return;
            }

            // Store initial positions and scales
            const initialPositions = pieces.map(piece => piece.position.clone());
            const initialScales = pieces.map(piece => piece.scale.x);
            const centerPosition = new THREE.Vector3(0, 0, 0);
            const targetMainScale = 1.0;

            // Make main blob visible and prepare it
            mainBlob.visible = true;
            mainBlob.position.copy(centerPosition);
            mainBlob.scale.setScalar(0.1); // Start small
            if (material.uniforms) {
                material.uniforms.uGlowIntensity.value = 0.0; // Start invisible
                material.uniforms.uListeningState.value = 0.0; // Silent mode style
                material.uniforms.uNoiseStrength.value = 0.18; // Silent mode noise
            }

            isTransitioningRef.current = true;
            const duration = 1000; // 1 second merge animation
            const startTime = performance.now();

            const animateMerge = (time: number) => {
                const progress = Math.min((time - startTime) / duration, 1);
                // Smooth easing
                const eased = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 3) / 2;

                // Animate pieces: move to center and fade out
                pieces.forEach((piece, i) => {
                    const startPos = initialPositions[i];
                    const startScale = initialScales[i];

                    // Move piece toward center
                    piece.position.lerpVectors(startPos, centerPosition, eased);

                    // Shrink piece as it moves to center
                    const targetScale = 0;
                    piece.scale.setScalar(THREE.MathUtils.lerp(startScale, targetScale, eased));

                    // Fade out piece
                    if (piece.material instanceof THREE.MeshStandardMaterial) {
                        piece.material.opacity = THREE.MathUtils.lerp(1.0, 0.0, eased);
                        piece.material.transparent = true;
                    }
                });

                // Animate main blob: grow from center and fade in
                const mainBlobScale = THREE.MathUtils.lerp(0.1, targetMainScale, eased);
                mainBlob.scale.setScalar(mainBlobScale);

                // Fade in main blob
                if (material.uniforms && material.uniforms.uGlowIntensity) {
                    material.uniforms.uGlowIntensity.value = eased;
                }

                // Render with error handling to suppress WebGL warnings
                try {
                    renderer.render(scene, camera);
                } catch (error) {
                    // Suppress WebGL errors during animation transitions
                    // These are typically harmless warnings about shader programs
                }

                if (progress < 1) {
                    transitionFrameRef.current = requestAnimationFrame(animateMerge);
                } else {
                    // Animation complete - remove pieces and restore main blob
                    // Remove all split pieces
                    pieces.forEach(piece => {
                        scene.remove(piece);
                    });
                    splitPiecesRef.current = [];

                    // Restore main blob to full state
                    mainBlob.scale.setScalar(targetMainScale);
                    if (material.uniforms) {
                        material.uniforms.uGlowIntensity.value = 1.0;
                        material.uniforms.uListeningState.value = 0.0; // Silent mode style (will be overridden by speaking state)
                        material.uniforms.uNoiseStrength.value = 0.18; // Base noise for speaking
                    }

                    isTransitioningRef.current = false;
                    transitionFrameRef.current = null;

                    // Final render with error handling
                    try {
                        renderer.render(scene, camera);
                    } catch (error) {
                        // Suppress WebGL errors during animation transitions
                    }
                }
            };

            transitionFrameRef.current = requestAnimationFrame(animateMerge);
        }

        prevStateRef.current = currentState;
    }, [blob.state]);

    // Animation loop for thinking state - animate the split pieces
    useEffect(() => {
        if (blob.state !== 'thinking') {
            return;
        }

        const pieces = splitPiecesRef.current;
        if (pieces.length === 0) {
            return;
        }

        // Initialize start time
        const startTime = performance.now() / 1000;
        const perPieceDuration = 0.5; // 0.5 seconds per piece
        const overlapRatio = 0.4; // Each piece starts at last 40% of previous one
        const startDelay = perPieceDuration * (1 - overlapRatio); // 0.3 seconds delay between starts
        const totalCycleDuration = perPieceDuration + (startDelay * (pieces.length - 1)); // Total cycle time
        const amplitude = 0.5; // 0.5 units up and down (1 unit total)

        let animationFrameId: number;

        const animateThinking = () => {
            if (blob.state !== 'thinking' || splitPiecesRef.current.length === 0) {
                return;
            }

            const currentTime = performance.now() / 1000;
            const elapsed = currentTime - startTime;
            const cycleTime = elapsed % totalCycleDuration;

            splitPiecesRef.current.forEach((piece, index) => {
                if (!piece) return;

                // Calculate when this piece's animation should start
                const pieceStartTime = index * startDelay;
                const pieceEndTime = pieceStartTime + perPieceDuration;

                // Check if this piece should be animating
                if (cycleTime >= pieceStartTime && cycleTime <= pieceEndTime) {
                    // This piece is in its animation phase
                    const localTime = cycleTime - pieceStartTime;
                    const phase = localTime / perPieceDuration; // 0 to 1
                    const eased = Math.sin(phase * Math.PI); // smooth up/down (0 to 1 to 0)
                    const targetY = amplitude * eased;
                    piece.position.y = THREE.MathUtils.lerp(piece.position.y, targetY, 0.8);
                } else if (cycleTime < pieceStartTime) {
                    // Piece hasn't started yet - keep at base
                    piece.position.y = THREE.MathUtils.lerp(piece.position.y, 0, 0.8);
                } else {
                    // Piece animation finished - return to base
                    piece.position.y = THREE.MathUtils.lerp(piece.position.y, 0, 0.8);
                }
            });

            // Force renderer update if available
            if (rendererRef.current && sceneRef.current && cameraRef.current) {
                rendererRef.current.render(sceneRef.current, cameraRef.current);
            }

            animationFrameId = requestAnimationFrame(animateThinking);
        };

        animationFrameId = requestAnimationFrame(animateThinking);

        return () => {
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
            }
        };
    }, [blob.state]);

    const hasImages = content.gallery.length > 0;

    return (
        <div
            className={`${styles.container} ${hasImages ? styles.withImages : ''}`}
        >
            <canvas ref={canvasRef} className={styles.canvas} />
        </div>
    );
}
