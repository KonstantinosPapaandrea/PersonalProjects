class BvhPlayer extends Animatable {
    /**
     * @param progressBar {ProgressBar}
     * @param annotationGraph {AnnotationGraph}
     * @param frames_per_second {number}
     * @param selectedFeatureKey {string}
     */
    constructor(
        progressBar,
        annotationGraph,
        frames_per_second = 24.98,
        selectedFeatureKey = "BODY"
    ) {
        super()
        this._progressBar = progressBar;
        this._progressBar.setUpdateCallback(this.gotoFrame.bind(this));
        this._progressBar.setTogglePlayCallback(this.togglePlay.bind(this));
        this._annotationGraph = annotationGraph;

        /**
         * @type {Object.<string, Animatable>}
         */
        this.animatables = {
            "progressBar": this._progressBar,
            "annotationGraph": this._annotationGraph
        }

        this.annotationComponents = {
            "annotationGraph": this._annotationGraph
        };
        this.featureKey = selectedFeatureKey;

        this._frame = 0;
        this.startTimeStamp = 0;
        this.previousTimeStamp = 0;

        this.timeElapsedSinceLastFrame = 0;
        this.frames_per_second = frames_per_second;
        this.currentAnimationFrame = null;
        this.timeSource = null;
        this.onPlayStateCallback = null;
        this.onFrameChangeCallback = null;
    }

    get frame() {
        return this._frame
    }

    get progressBar() {
        return this._progressBar;
    }

    get annotationGraph() {
        return this._annotationGraph;
    }

    set frames_per_second(value) {
        this._frames_per_second = value;
        this._seconds_per_frame = 1 / value;
    }

    get frames_per_second() {
        return this._frames_per_second;
    }

    get seconds_per_frame() {
        return this._seconds_per_frame;
    }

    /**
     * @param callback {(() => (number | null)) | null}
     */
    setTimeSource(callback) {
        this.timeSource = typeof callback === "function" ? callback : null;
    }

    /**
     * @param callback {((boolean) => void) | null}
     */
    setPlayStateCallback(callback) {
        this.onPlayStateCallback = typeof callback === "function" ? callback : null;
    }

    /**
     * @param callback {((number) => void) | null}
     */
    setFrameChangeCallback(callback) {
        this.onFrameChangeCallback = typeof callback === "function" ? callback : null;
    }

    updatePlayPauseIcon() {
        if (this._progressBar && this._progressBar.playPauseIcon) {
            this._progressBar.playPauseIcon.className = this._progressBar.playing
                ? "fas fa-pause"
                : "fas fa-play";
        }
    }

    /**
     * @param value {string}
     */
    set featureKey(value) {
        this._featureKey = value;
        Object.values(this.annotationComponents).forEach(c => c.featureKey = this.featureKey);
        this.reset(this.frame)
    }

    get featureKey() {
        return this._featureKey;
    }

    /**
     * @param id {string}
     * @param annotationComponent
     */
    addAnnotationComponent(id, annotationComponent) {
        this.annotationComponents[id] = annotationComponent;
    }

    /**
     * @param id {string}
     * @param animatable {Animatable}
     */
    addAnimatable(id, animatable) {
        this._progressBar.enable()
        this.animatables[id] = animatable;
        // set the progress bar frames to the maximum of all animatables ( except the progressBar itself )
        const maxFrames = Object.entries(this.animatables)
            .reduce((max, [key, animatable]) => {
                if (key === "progressBar") {
                    return 0;
                }
                let numFrames = animatable.getNumFrames();
                return numFrames > max ? numFrames : max;
        }, 0);
        this.progressBar.setNumFrames(maxFrames);
        this.annotationGraph.graphFrames = maxFrames;
        if (this.frame >= maxFrames) {
            this.gotoFrame(maxFrames - 1)
        }
    }

    getNumFrames() {
        const maxFrames = Object.values(this.animatables).reduce((max, obj) => {
            let numFrames = obj.getNumFrames();
            return numFrames > max ? numFrames : max;
        }, 0);
        return maxFrames;
    }

    /**
     * @param frame {number}
     */
    gotoFrame(frame, suppressCallback = false) {
        super.gotoFrame(frame)

        Object.values(this.animatables).forEach(a => a.gotoFrame(frame))
        if (!suppressCallback && this.onFrameChangeCallback) {
            this.onFrameChangeCallback(this.frame);
        }
    }

    setPlaying(playing) {
        const nextPlaying = !!playing;
        if (this._progressBar.playing === nextPlaying) {
            this.updatePlayPauseIcon();
            return;
        }

        this._progressBar.playing = nextPlaying;
        if (this._progressBar.playing) {
            this.startTimeStamp = performance.now()
            this.previousTimeStamp = this.startTimeStamp
            this.timeElapsedSinceLastFrame = 0;
            this.currentAnimationFrame = requestAnimationFrame(this.updateHelper.bind(this));
        } else {
            if (this.currentAnimationFrame) {
                cancelAnimationFrame(this.currentAnimationFrame);
            }
            this.currentAnimationFrame = null;
            this.startTimeStamp = 0;
            this.previousTimeStamp = 0;
        }

        this.updatePlayPauseIcon();
        if (this.onPlayStateCallback) {
            this.onPlayStateCallback(this._progressBar.playing);
        }
    }

    togglePlay() {
        this.setPlaying(!this._progressBar.playing);
    }

    /**
     * @param deltaTime {number}
     */
    update(deltaTime) {
        if (this.timeSource) {
            const externalSeconds = this.timeSource();
            if (Number.isFinite(externalSeconds)) {
                const targetFrame = Math.round(externalSeconds * this.frames_per_second);
                if (targetFrame !== this.frame) {
                    this.gotoFrame(targetFrame, true);
                }
                return;
            }
        }

        this.timeElapsedSinceLastFrame += deltaTime;

        if (this.timeElapsedSinceLastFrame >= this.seconds_per_frame) {
            const framesToAdvance = Math.floor(this.timeElapsedSinceLastFrame / this.seconds_per_frame);
            this.gotoFrame(this.frame + framesToAdvance)
            this.timeElapsedSinceLastFrame -= this.seconds_per_frame * framesToAdvance;
        }
    }

    /**
     * @param currentTimeStamp {number}
     */
    updateHelper(currentTimeStamp) {
        if (!this.startTimeStamp) {
            this.startTimeStamp = performance.now();
        }

        const deltaTime = (currentTimeStamp - this.previousTimeStamp) / 1000;
        this.update(deltaTime)
        this.previousTimeStamp = currentTimeStamp;

        if (this._progressBar.playing) {
            this.currentAnimationFrame = requestAnimationFrame(this.updateHelper.bind(this));
        } else {
            this.currentAnimationFrame = null;
        }
    }

    /**
     * @param frameAfterReset {number | null}
     */
    reset(frameAfterReset = null) {
        this.gotoFrame(1)
        Object.values(this.animatables).forEach(a => a.reset())
        Object.values(this.annotationComponents).forEach(a => a.reset())
        if (frameAfterReset) {
            this.gotoFrame(frameAfterReset)
        }
    }
}

(function($, window, document) {

    /**
     * @param annotationInputId {string}
     * @param bvhInputId {string}
     * @param color {string}
     * @returns {jQuery|HTMLElement|*}
     */
    function createAnnotationContainer(
        annotationInputId,
        bvhInputId,
        color =  "#007BFF"

) {
        const annotationBlock =  $(`
            <div class="annotationBlock">
                <div class="visualization">
                    <div class="valueDisplay">0.00</div>
                    <div class="barContainer">
                        <div class="featureBar"></div>
                    </div>
                </div>
                <label for="${annotationInputId}" class="customFileUpload">
                    <i class="fas fa-file"></i>
                    <input type="file" id="${annotationInputId}" class="annotationFile" accept="application/json" />
                </label>
                <label for="${bvhInputId}" class="customFileUpload bvh">
                    <i class="fas fa-walking"></i>
                    <input type="file" id="${bvhInputId}" class="annotationFile" accept=".bvh" />
                </label>
            </div>
        `)
        annotationBlock.find(".customFileUpload").css("backgroundColor", color)
        annotationBlock.find(".featureBar").css("backgroundColor", color)

        return annotationBlock
    }

    $(function() {
        const vsize = {x: 100, y: 100, z: 0};
        let mouse = {x: 0, y: 0};
        let lightPos, camPos;

        const FAR = 2000;

        const ToRad = Math.PI / 180;
        const ToDeg = 180 / Math.PI;

        let camera, container, scene, renderer, center, centerLight;
        let ambient, hemiLight, pointLight, light;

        let ground;

        let gui;
        const animConfig = {
            current: "none",
            idle: false,
            walk: true,
            salut: false,
            speed: 0.8
        };

        let sky;

        let debug;

        const bvhReader = null;

        const SeaStandard = false;

        function init() {

            out1 = document.getElementById("output1");
            out2 = document.getElementById("output2");

            vsize.x = window.innerWidth;
            vsize.y = window.innerHeight;
            vsize.z = vsize.x / vsize.y;

            camPos = { horizontal: 90, vertical: 65, distance: 200, automove: false };
            lightPos = { horizontal: 135, vertical: 35, distance: 200 };
            mouse = { ox:0, oy:0, h:0, v:0, mx:0, my:0, down:false, over:false, moving:true, dx:0, dy:0 };

            if(SeaStandard)lightPos.horizontal+=180;

            debug = document.getElementById("debug");

            addGUI();

            initScene3D();
        }

        function debugTell(s) {
            debug.innerHTML = s;
        }

        function initScene3D() {

            // RENDERER
            renderer = new THREE.WebGLRenderer({  antialias: false });
            renderer.setSize( vsize.x, vsize.y );
            renderer.autoClear = false;
            //renderer.sortObjects = false;
            renderer.gammaInput = true;
            renderer.gammaOutput = true;
            renderer.shadowMapEnabled = true;
            //renderer.shadowMapCullFace = THREE.CullFaceBack;
            renderer.shadowMapType = THREE.PCFSoftShadowMap;

            container = document.getElementById("viewport");
            container?.appendChild( renderer.domElement );
            renderer.domElement.style.top = 0 + "px";
            renderer.domElement.style.left = 0 + "px";
            renderer.domElement.style.position = "absolute";

            // SCENE
            scene = new THREE.Scene();

            // CAMERA
            camera = new THREE.PerspectiveCamera( 45, vsize.z, 1, FAR );
            //camera.position.set( 0, 30, 100 );
            center = new THREE.Vector3(0, -15, 0);
            centerLight =  new THREE.Vector3(0,-45,0);
            moveCamera();


            addBasicObject();

            initLightAndSky();

            //importBody();

            window.addEventListener( 'resize', resize, false );
            container.addEventListener( 'mousemove', onMouseMove, false );
            container.addEventListener( 'mousedown', onMouseDown, false );
            container.addEventListener( 'mouseout', onMouseUp, false );
            container.addEventListener( 'mouseup', onMouseUp, false );

            const body = document.body;
            if( body.addEventListener ){
                body.addEventListener( 'mousewheel', onMouseWheel, false ); //chrome
                body.addEventListener( 'DOMMouseScroll', onMouseWheel, false ); // firefox
            }else if( body.attachEvent ){
                body.attachEvent("onmousewheel" , onMouseWheel); // ie
            }
            animate();
        }

        //-----------------------------------------------------
        //
        //  RENDER LOOP
        //
        //-----------------------------------------------------

        function animate() {
            requestAnimationFrame( animate );
            render();
        }

        function render() {
            updateBVH();
            renderer.clear();
            renderer.render( scene, camera );
        }

        //-----------------------------------------------------
        //  LISTENER
        //-----------------------------------------------------

        function resize( event ) {
            vsize.x = window.innerWidth;
            vsize.y = window.innerHeight;
            vsize.z = vsize.x / vsize.y;
            camera.aspect = vsize.z;
            camera.updateProjectionMatrix();
            renderer.setSize( vsize.x, vsize.y );
        }

        //-----------------------------------------------------
        //  LIGHT & SKY
        //-----------------------------------------------------

        function initLightAndSky(){

            ambient = new THREE.AmbientLight( 0x202020 );
            scene.add( ambient );

            hemiLight = new THREE.HemisphereLight( 0x202020, 0xffffff, 1 );
            hemiLight.position.set( 0, 20, 0 );
            scene.add( hemiLight );

            pointLight = new THREE.PointLight( 0xFFFFFF, 1, 600 );
            scene.add( pointLight );

            light = new THREE.SpotLight( 0xFFFFFF, 1, 0, Math.PI/2, 1 );
            light.castShadow = true;
            light.onlyShadow = false;
            light.shadowCameraNear = 50;
            light.shadowCameraFar = 500;
            //light.shadowCameraFov = 35;
            light.shadowBias = -0.005;
            light.shadowMapWidth = light.shadowMapHeight = 1024;
            light.shadowDarkness = 0.35;

            moveLight();

            //light.shadowCameraVisible = true;

            scene.add( light );
        }

        function moveLight() {
            light.position.copy(Orbit(centerLight, lightPos.horizontal, lightPos.vertical, lightPos.distance));
            pointLight.position.copy(Orbit(centerLight, lightPos.horizontal+180, lightPos.vertical+180, lightPos.distance));
            light.lookAt(centerLight);
        }

        function lightColors( cc ){
            ambient.color.setHex(cc[2]);

            hemiLight.color.setHex( cc[2] );
            hemiLight.groundColor.setHex( cc[0] );

            pointLight.color.setHex( cc[1] );

            light.color.setHex( cc[3] );

            currentColors = cc;
        }

        function addBasicObject() {
            const skyMaterial = new THREE.MeshBasicMaterial({color: 0x303030, side: THREE.BackSide, depthWrite: false});
            sky = new THREE.Mesh( new THREE.BoxGeometry( FAR, FAR, FAR ), skyMaterial );
            scene.add( sky );

            const groundMaterial = new THREE.MeshBasicMaterial({color: 0xFFFFFF, transparent: true});
            const blendings = ["NoBlending", "NormalBlending", "AdditiveBlending", "SubtractiveBlending", "MultiplyBlending", "AdditiveAlphaBlending"];
            groundMaterial.blending = THREE[ blendings[ 4 ] ];
            ground = new THREE.Mesh(new THREE.PlaneGeometry( 1000, 1000, 4, 4 ), groundMaterial);
            ground.position.set( 0, 0, 0 );
            ground.rotation.x = - Math.PI / 2;
            ground.receiveShadow = true;
            scene.add( ground );

            const helper2 = new THREE.GridHelper(100, 50);
            helper2.setColors( 0x00ff00, 0x888888 );
            scene.add( helper2 );
        }

        //-----------------------------------------------------
        //  BVH TEST
        //-----------------------------------------------------

        const BVHset = {ax:"x", ay:"y", az:"z", dx:1, dy:1, dz:1, rx:0, ry:0, rz:0, order:"XYZ"};
        const BVHanimConfig = {
            debug:true,
            speed:1.3,
            size:1,
            px:0,
            py:-22,
            pz:0,
            boneSize:0.83
        }

        function loadBVH(name) {
            bvhReader.load(`res/bvh/${name}`)
        }

        function initBVHGui(bvhReader) {
            const f5 = gui.addFolder(`BVH Animation BETA ${bvhReader.name}`);

            BVHanimConfig.calibration = function() { loadBVH("calibration.png"); };
            BVHanimConfig.ballet = function() { loadBVH("ballet.png"); };
            BVHanimConfig.shoot = function() { loadBVH("shoot.png"); };
            BVHanimConfig.sprint = function() { loadBVH("sprint.png"); };
            BVHanimConfig.exsize = function() { loadBVH("exsize.png"); };
            BVHanimConfig.test = function() { loadBVH("test.png"); };
            BVHanimConfig.big = function() { loadBVH("big.png"); };

            BVHanimConfig.c11A = function() { loadBVH("c11A.png"); };
            BVHanimConfig.c11B = function() { loadBVH("c11B.png"); };

            BVHanimConfig.dance = function() { loadBVH("dance.png"); };

            BVHanimConfig.stop = null
            BVHanimConfig.play = null
            BVHanimConfig.next = function() { bvhReader.next(); };
            BVHanimConfig.prev = function() { bvhReader.prev(); };

            f5.add( BVHanimConfig, 'speed', 0.01, 2 ).onChange( function() { bvhReader.speed = BVHanimConfig.speed; });;
            f5.add( BVHanimConfig, 'size', 1, 10 ).onChange( function() { bvhReader.reScale(BVHanimConfig.size) });
            // f5.add( BVHanimConfig, 'px', -100, 100 ).onChange( function() { positionBVH() });;
            // f5.add( BVHanimConfig, 'py', -100, 100 ).onChange( function() { positionBVH() });;
            // f5.add( BVHanimConfig, 'pz', -100, 100 ).onChange( function() { positionBVH() });;
            f5.add( BVHanimConfig, 'boneSize', 0.1, 5 ).onChange( function() { bvhReader.boneSize = BVHanimConfig.boneSize; });
            f5.open();
        }

        // function positionBVH() {
        //     bvhReader.rePosition(new THREE.Vector3( BVHanimConfig.px || 0, BVHanimConfig.py|| 0, BVHanimConfig.pz|| 0 ))
        // }

        function updateBVH() {
            if(bvhReader !== null && bvhReader.play){

                bvhReader.update();
            }
        }

        const annotationColors = [
            "#1f77b4ff",
            "#ff7f0ee5",
            "#2ca02ccc",
            "#d62728b3",
            "#9467bdbf",
            "#8c56407f",
            "#e377c2b3",
            "#7f7f7f4c",
            "#bcbd2220",
            "#17becf1a"
        ]
        const motionColours = annotationColors.map(c => c.slice(0, c.length - 2))

        let graphLineColourIdx = 0;


        function toAngles(o) {
            const q = o.quaternion.clone();
            const x = q.x,
                y = q.y,
                z = q.z,
                w = q.w;

            let a = 2 * (w * y - z * x);

            if (a < -1) a = -1;
            else if (a > 1) a = 1;

            return {
                x : Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)) * 1,
                y : Math.asin(a) * 1,
                z : Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)) * 1
            }
        }

        function traceMatrix(o, n) {
            const e = o.matrix.elements;
            let s = o.name + "<br>";
            const q = o.quaternion.clone();
            //s+=( q.x ).toFixed(2)+ "_"+ ( q.y ).toFixed(2) +  "_"+ (q.z).toFixed(2)+ "_"+  (q.w).toFixed(2);
            //s+=( b.rot.x * ToDeg ).toFixed(2)+ "_"+ ( b.rot.y * ToDeg ).toFixed(2) +  "_"+ ( b.rot.z * ToDeg ).toFixed(2);

            //s+= "<br>"

            s+=( o.rotation.x * ToDeg ).toFixed(2)+ "_"+ ( o.rotation.y * ToDeg ).toFixed(2) +  "_"+ ( o.rotation.z * ToDeg ).toFixed(2)+ "_"+ o.rotation.order;

            s+= "<br>"

            s += "_"+ e[0].toFixed(2) + "_" + e[1].toFixed(2) + "_"+ e[2].toFixed(2) + "_" + e[3] + "<br>";
            s += "_"+ e[4].toFixed(2) + "_" + e[5].toFixed(2) + "_"+ e[6].toFixed(2) + "_" + e[7] + "<br>";
            s += "_"+ e[8].toFixed(2) + "_" + e[9].toFixed(2) + "_"+ e[10].toFixed(2) + "_" + e[11] + "<br>";
            s += "_"+ e[12] + "_" + e[13] + "_"+ e[14] + "_" + e[15] + "<br>";

            if(n===1) out1.innerHTML = s;
            else out2.innerHTML = s;
        }



        //-----------------------------------------------------
        //  GUI
        //-----------------------------------------------------

        function addGUI() {
            gui = new dat.GUI({autoPlace:false, width:204});
            document.getElementById('gui')?.appendChild(gui.domElement);
        }

        function tell(s){
            document.getElementById("debug").innerHTML = s;
        }



        //-----------------------------------
        // MATH
        //-----------------------------------

        function Orbit(origine, horizontal, vertical, distance) {
            const p = new THREE.Vector3();
            const phi = vertical * ToRad;
            const theta = horizontal * ToRad;
            p.x = (distance * Math.sin(phi) * Math.cos(theta)) + origine.x;
            p.z = (distance * Math.sin(phi) * Math.sin(theta)) + origine.z;
            p.y = (distance * Math.cos(phi)) + origine.y;
            return p;
        }

        //-----------------------------------
        // MOUSE & NAVIGATION
        //-----------------------------------

        const changeView = function (h, v, d) {
            TweenLite.to(camPos, 3, {horizontal: h, vertical: v, distance: d, onUpdate: moveCamera});
            camPos.automove = true;
        };

        function moveCamera() {
            camera.position.copy(Orbit(center, camPos.horizontal, camPos.vertical, camPos.distance));
            camera.lookAt(center);
        }

        function onMouseDown(e) {
            e.preventDefault();
            mouse.ox = e.clientX;
            mouse.oy = e.clientY;
            mouse.h = camPos.horizontal;
            mouse.v = camPos.vertical;
            mouse.down = true;
        }

        function onMouseUp(e) {
            mouse.down = false;
            document.body.style.cursor = 'auto';
        }

        function onMouseMove(e) {
            e.preventDefault();
            if (mouse.down ) {
                document.body.style.cursor = 'move';
                if(SeaStandard)camPos.horizontal = (-(e.clientX - mouse.ox) * 0.3) + mouse.h;
                else camPos.horizontal = ((e.clientX - mouse.ox) * 0.3) + mouse.h;
                camPos.vertical = (-(e.clientY - mouse.oy) * 0.3) + mouse.v;

                moveCamera();
            } else {
                mouse.ox = e.clientX;
                mouse.oy = e.clientY;
            }
        }

        function onMouseWheel(e) {
            let delta = 0;
            if(e.wheelDelta){delta=e.wheelDelta*-1;}
            else if(e.detail){delta=e.detail*20;}
            camPos.distance+=(delta/10);

            moveCamera();
            e.preventDefault();
        }

        /**
         * @param bvhReader {BVHReader}
         */
        function initBVH(bvhReader) {
            bvhReader.initUI('progressBar', 'playPauseButton', "featureBar");
            bvhReader.speed = BVHanimConfig.speed;

            // loadBVH("action.png");

            // initBVHGui(bvhReader);
        }

        // fit a rect into some container, keeping the aspect ratio of the rect
        function fitRectIntoContainer (rectWidth, rectHeight, containerWidth, containerHeight) {

            const widthRatio = containerWidth / rectWidth;    // ratio container width to rect width
            const heightRatio = containerHeight / rectHeight; // ratio container height to rect height

            const ratio = Math.min( widthRatio, heightRatio ); // take the smaller ratio

            // new rect width and height, scaled by the same ratio
            return {
                width: rectWidth * ratio,
                height: rectHeight * ratio,
            };
        }

        /**
         *
         * @param canvas {HTMLCanvasElement}
         * @param width {number}
         * @param height {number}
         */
        function resizeCanvas(canvas, width, height) {
            // Set the canvas drawing surface width and height
            canvas.width = width;
            canvas.height = height;

            // Optionally set the CSS width and height
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;

            // Optionally, redraw or reinitialize your canvas content
            const ctx = canvas.getContext('2d');
            if (ctx) {
                ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear the canvas
                // Redraw content here if needed
            }
        }
        const graphCanvas = $("canvas#graphCanvas")
        const graphCanvasElement = graphCanvas.get(0)
        const canvasContainer = $("#progressContainer")
        // const canvasSize = fitRectIntoContainer(
        //     graphCanvas.width(),
        //     graphCanvas.height(),
        //     canvasContainer.width(),
        //     canvasContainer.height()
        // );
        // resizeCanvas(graphCanvasElement, canvasSize.width, canvasSize.height)

        const progressBar = new ProgressBar('progressBar', 'playPauseButton');
        const annotationGraph = new AnnotationGraph(graphCanvasElement)
        const bvhPlayer = new BvhPlayer(progressBar, annotationGraph);
        window.bvhPlayer = bvhPlayer;
        /**
         * @type {Object.<string, BVHReader>}
         */
        const bvhReaders = {}
        window.bvhReaders = bvhReaders;

        /**
         * @param event {Event}
         * @param bvhReaderId {string}
         * @param color {string}
         * @param resetPosition {THREE.Vector3}
         */
     function handleBvhFileInput(
    event,
    bvhReaderId,
    color,
    resetPosition
) {
    color = color.slice(0, 7)
    const files = event.target.files;
    if (!files) return;

    for (const file of files) {
        window.dispatchEvent(new CustomEvent("m2m:bvh-file-selected", {
            detail: {
                file,
                fileName: file.name,
                bvhReaderId,
            }
        }));
        const reader = new FileReader();
        const material = new THREE.MeshLambertMaterial({ color }, color);
        reader.onload = function(e) {
            const bvhReader = bvhReaders[bvhReaderId] || new BVHReader(scene, material, resetPosition);
            bvhReaders[bvhReaderId] = bvhReader;
            initBVH(bvhReader);

            // ⬇️ remove the stray '+' and keep this exact call
            bvhReader.parseData(e.target.result.split(/\s+/g));

            // Sync playback to the BVH file's native FPS
            const nativeFps = 1 / bvhReader.secsPerFrame;
            bvhPlayer.frames_per_second = nativeFps;

            // Add motion source to the player -> updates progressBar/graphFrames
            bvhPlayer.addAnimatable(bvhReaderId, bvhReader);

            // Make graph timeline match the (possibly new) BVH length
           const maxFrames = bvhPlayer.getNumFrames();
annotationGraph.graphFrames = maxFrames;

Object.values(bvhPlayer.annotationComponents).forEach(c => {
  if (c && ('targetFrames' in c)) {
    c.targetFrames = maxFrames;
  }
});

            // Refresh visuals and keep current frame if possible
            annotationGraph.clearGraph();
            annotationGraph.drawGraph();
            bvhPlayer.reset(bvhPlayer.frame);

            window.dispatchEvent(new CustomEvent("m2m:bvh-loaded", {
                detail: {
                    fileName: file.name,
                    bvhReaderId,
                    nativeFps,
                    numFrames: bvhReader.getNumFrames(),
                    secsPerFrame: bvhReader.secsPerFrame,
                }
            }));
        };
        reader.readAsText(file);
    }
}


        let annotationContainerCount = 0

        const annotatorIds = [0, 1, 2];
        annotatorIds.forEach(createAnnotationBlock)

        function activateAnnotationButtons() {
            const buttons = $("#annotationButtonsContainer .annotationButtons .btn")
            const isAnyButtonDisabled = buttons.filter(":disabled").length > 0
            if (!isAnyButtonDisabled) {
                return
            }

            buttons.each(function() {
                $(this).prop("disabled", false);
            })

            buttons.click(function() {
                buttons.removeClass('selected');
                $(this).addClass('selected');
                const selectedFeatureKey = $(this).text();
                bvhPlayer.featureKey = selectedFeatureKey;
            });
            buttons.first().trigger('click');
        }

        /**
         * @param values {string[]}
         */
        function populateAnnotationButtonList(values) {
            const buttonList = $("#annotationButtonsContainer .annotationButtons").first()
            if (!buttonList) return;
            if (buttonList.find("button.btn").length > 0) return;

            buttonList.empty()
            values.forEach(
                v => {
                    const btn = `<button class="btn">${v}</button>`
                    buttonList.append(btn)
                }
            )

            const annotationButtons = $('#annotationButtonsContainer .btn')
            annotationButtons.click(function() {
                annotationButtons.removeClass('selected');
                $(this).addClass('selected');
                const selectedFeatureKey = $(this).text();
                bvhPlayer.featureKey = selectedFeatureKey;
            });
            annotationButtons.first().trigger('click');
        }

        const resetPositions = [
            new THREE.Vector3(40, BVHanimConfig.py, 0),
            new THREE.Vector3(0, BVHanimConfig.py, 0),
            new THREE.Vector3(-40, BVHanimConfig.py, 0),
        ]
        /**
         * @param id {number}
         * @returns {Window.jQuery|HTMLElement|*}
         */
        function createAnnotationBlock(id) {
            const annotationInputId = `annotationInput-${id}`;
            const bvhInputId = `bvhInput-${id}`;
            const annotationColor = annotationColors[id];
            const newAnnotationContainer = createAnnotationContainer(
                annotationInputId,
                bvhInputId,
                annotationColor
            );
            $('#annotationContainer').append(newAnnotationContainer);

            newAnnotationContainer
                .find(`#${bvhInputId}`)
                .on("change", function(e) {
                    const motionColor = motionColours[id];
                    const bvhReaderId = `bvhReader-${id}`
                    const resetPosition = resetPositions[id]
                    handleBvhFileInput(e, bvhReaderId, motionColor, resetPosition)
                })
            newAnnotationContainer
                .find(`#${annotationInputId}`)
                .on('change', function (evt) {
                    const file = evt.target.files[0];
                    if (!file) return;

                    const reader = new FileReader();
                    reader.onload = function (e) {
                        try {
                            const motionData = JSON.parse(e.target.result);
                            const annotationGraphLine = new AnnotationGraphLine(
                                graphCanvasElement,
                                motionData,
                                bvhPlayer.featureKey,
                                annotationColor,
                                5
                            )
                            const valueDisplayElement = newAnnotationContainer
                                .find(".valueDisplay")
                                .get(0)
                            const featureBarElement = newAnnotationContainer
                                .find(".featureBar")
                                .get(0)
                            const valueDisplay = new ValueDisplay(valueDisplayElement)
                            const featureBar  = new FeatureBar(featureBarElement, 0, annotationColor)
                            const annotationBar = new AnnotationBar(
                                motionData,
                                featureBar,
                                valueDisplay,
                                bvhPlayer.featureKey,
                                annotationColor,
                            )
                            annotationBar.targetFrames = bvhPlayer.getNumFrames();

                            bvhPlayer.addAnnotationComponent(id.toString(), annotationBar)
                            // const motionKeys = Object.keys(motionData).filter(key => !["START_FRAME", "END_FRAME"].includes(key));
                            // populateAnnotationButtonList(motionKeys)
                            activateAnnotationButtons()
                            annotationGraph.graphFrames = bvhPlayer.getNumFrames()
                            annotationGraph.addGraphLine(id.toString(), annotationGraphLine)
                            // bvhPlayer.progressBar.setNumFrames(annotationGraph.getNumFrames())
                            annotationGraph.graphFrames = bvhPlayer.getNumFrames()
                            annotationGraph.clearGraph()
                            annotationGraph.drawGraph()
                            bvhPlayer.addAnimatable(id.toString(), annotationBar)
                            bvhPlayer.reset(bvhPlayer.frame)
                        } catch (error) {
                            console.error(error)
                        }
                    };
                    reader.readAsText(file);
                });
            return newAnnotationContainer;
        }

        init()
    });

}(window.jQuery, window, document));
