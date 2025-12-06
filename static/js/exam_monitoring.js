let video, canvas, ctx;
let faceMesh;
let lastWarningTime = 0;
let faceDetectionCount = 0;
let noFaceCount = 0;
let lookAwayCount = 0;

let hasFocus = true;
let monitoringActive = true;  // <--- important flag added

function initMonitoring() {
    video = document.getElementById('video-feed');
    canvas = document.getElementById('canvas');
    ctx = canvas.getContext('2d');

    window.addEventListener('blur', () => {
        if (!monitoringActive) return;
        hasFocus = false;
        handleViolation('You switched tabs or applications');
        updateStatus('focus', 'danger', 'Focus: Lost ✗');
    });

    window.addEventListener('focus', () => {
        if (!monitoringActive) return;
        hasFocus = true;
        updateStatus('focus', 'ok', 'Focus: Active ✓');
    });

    document.addEventListener('visibilitychange', () => {
        if (!monitoringActive) return;

        if (document.hidden) {
            hasFocus = false;
            handleViolation('You left the exam tab');
            updateStatus('focus', 'danger', 'Focus: Lost ✗');
        } else {
            hasFocus = true;
            updateStatus('focus', 'ok', 'Focus: Active ✓');
        }
    });

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
            video.play();
            
            video.addEventListener('loadedmetadata', () => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                startFaceDetection();
            });
        })
        .catch(err => {
            console.error('Error accessing webcam:', err);
            alert('Webcam access is required for this exam. Please allow camera access and refresh.');
        });
}

function startFaceDetection() {
    faceMesh = new FaceMesh({
        locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619/${file}`;
        }
    });
    
    faceMesh.setOptions({
        maxNumFaces: 2,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    faceMesh.onResults(onFaceResults);

    async function detectFrame() {
        if (!monitoringActive) return;   // <--- prevents loop after submit
        await faceMesh.send({image: video});
        requestAnimationFrame(detectFrame);
    }
    
    detectFrame();
}

function onFaceResults(results) {
    if (!monitoringActive) return;   // <--- stops warnings after submit

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
        const landmarks = results.multiFaceLandmarks[0];
        
        if (results.multiFaceLandmarks.length > 1) {
            handleViolation('Multiple faces detected');
            updateStatus('face', 'danger', 'Multiple Faces ✗');
            logMonitoringEvent('MULTIPLE_FACES', false, 'Multiple', 'Unknown');
            return;
        }
        
        faceDetectionCount++;
        noFaceCount = 0;
        
        const gazeDirection = analyzeGaze(landmarks);
        const headPose = analyzeHeadPose(landmarks);
        
        if (gazeDirection === 'Away' || headPose === 'Looking Away') {
            lookAwayCount++;
            if (lookAwayCount > 10) {
                handleViolation('Looking away from screen');
                updateStatus('gaze', 'danger', 'Gaze: Away ✗');
                lookAwayCount = 0;
            } else {
                updateStatus('gaze', 'warning', 'Gaze: Check Position ⚠');
            }
        } else {
            lookAwayCount = 0;
            updateStatus('gaze', 'ok', 'Gaze: Centered ✓');
        }
        
        updateStatus('face', 'ok', 'Face: Detected ✓');
        
        if (faceDetectionCount % 30 === 0) {
            logMonitoringEvent('MONITORING_CHECK', true, gazeDirection, headPose);
        }
        
    } else {
        noFaceCount++;
        
        if (noFaceCount > 15) {
            handleViolation('Face not detected');
            updateStatus('face', 'danger', 'Face: Not Detected ✗');
            noFaceCount = 0;
        } else {
            updateStatus('face', 'warning', 'Face: Checking... ⚠');
        }
        
        logMonitoringEvent('NO_FACE', false, 'None', 'None');
    }
}

function analyzeGaze(landmarks) {
    const leftEye = landmarks[33];
    const rightEye = landmarks[263];
    const nose = landmarks[1];
    
    const eyeCenterX = (leftEye.x + rightEye.x) / 2;
    const eyeCenterY = (leftEye.y + rightEye.y) / 2;
    
    const horizontalDiff = Math.abs(eyeCenterX - nose.x);
    const verticalDiff = Math.abs(eyeCenterY - nose.y);
    
    if (horizontalDiff > 0.05 || verticalDiff > 0.08) {
        return 'Away';
    }
    
    return 'Center';
}

function analyzeHeadPose(landmarks) {
    const leftEar = landmarks[234];
    const rightEar = landmarks[454];
    const nose = landmarks[1];
    
    const earDistance = Math.abs(leftEar.x - rightEar.x);
    
    if (earDistance < 0.15) {
        return 'Looking Away';
    }
    
    if (nose.y < 0.3 || nose.y > 0.7) {
        return 'Head Tilted';
    }
    
    return 'Forward';
}

function updateStatus(type, status, text) {
    const element = document.getElementById(`${type}-status`);
    if (!element) return;
    element.className = `status-indicator status-${status}`;
    element.textContent = text;
}

function handleViolation(message) {
    if (!monitoringActive) return;  // <--- CRITICAL FIX

    const now = Date.now();
    if (now - lastWarningTime < 5000) return;

    lastWarningTime = now;

    fetch('/student/issue-warning', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        warningCount = data.warnings;
        document.getElementById('warning-count').textContent = warningCount;
        
        const violationAlert = document.getElementById('violation-alert');
        const violationMessage = document.getElementById('violation-message');
        
        violationMessage.textContent = `Warning ${warningCount}: ${message}`;
        violationAlert.style.display = 'block';
        
        setTimeout(() => {
            violationAlert.style.display = 'none';
        }, 5000);
        
        if (data.terminate) {
            stopMonitoring();  
            alert('You have received 3 warnings. Your exam is being submitted automatically.');
            submitExam('violations');
        }
    });
}

function logMonitoringEvent(eventType, faceDetected, gazeDirection, headPose) {
    if (!monitoringActive) return;

    fetch('/student/log-monitoring', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            event_type: eventType,
            face_detected: faceDetected ? 1 : 0,
            gaze_direction: gazeDirection,
            head_pose: headPose
        })
    });
}


function stopMonitoring() {
    monitoringActive = false;


    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
    }

    // Stop FaceMesh
    if (faceMesh) {
        faceMesh.close();
    }
}


function submitExam(reason = 'manual') {
    stopMonitoring();  

    fetch('/student/submit-exam', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ reason })
    }).then(() => {
        window.location.href = '/student/exam-finished';
    });
}
